"""Quota service for usage tracking and enforcement."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quota import OrganizationQuota, UsageLog
from app.models.organization import Organization
from app.models.subscription import Subscription


class QuotaService:
    """Service for managing organization quotas."""

    @staticmethod
    async def check_subscription_active(
        db: AsyncSession, organization_id: uuid.UUID
    ) -> tuple[bool, str | None]:
        """
        Check if organization has an active subscription.

        Returns:
            (is_active, error_message)
        """
        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == organization_id)
        )
        subscription = result.scalar_one_or_none()

        if not subscription:
            return False, "No subscription found"

        if subscription.status == "canceled":
            return False, "Subscription has been canceled. Please reactivate to continue."

        if subscription.status == "past_due":
            return (
                False,
                "Payment failed. Please update your payment method to continue using the service.",
            )

        if subscription.status in ["unpaid", "incomplete", "incomplete_expired"]:
            return False, "Subscription payment incomplete. Please complete payment setup."

        # Active or trialing is OK
        return True, None

    @staticmethod
    async def check_quota_with_subscription(
        db: AsyncSession,
        organization_id: uuid.UUID,
        quota_type: str,
        amount: int = 1,
    ) -> tuple[bool, str | None]:
        """
        Check quota with subscription validation.

        Args:
            db: Database session
            organization_id: Organization UUID
            quota_type: Type of quota to check (users, storage, api_calls, file_uploads)
            amount: Amount to check (e.g., file size in bytes for storage)

        Returns:
            (allowed: bool, error_message: str | None)
        """
        # First check subscription status
        is_active, error = await QuotaService.check_subscription_active(db, organization_id)
        if not is_active:
            return False, error

        # Get quota
        quota = await QuotaService.get_or_create_quota(db, organization_id)

        # Reset quotas if needed
        if quota_type in ["api_calls", "storage"]:
            quota = await QuotaService.check_and_reset_monthly_quotas(db, quota)
        elif quota_type == "file_uploads":
            quota = await QuotaService.check_and_reset_daily_quotas(db, quota)

        # Check specific quota type
        if quota_type == "users":
            if quota.max_users != -1 and quota.current_users >= quota.max_users:
                return (
                    False,
                    f"User limit reached ({quota.max_users}). Please upgrade your plan to add more users.",
                )

        elif quota_type == "storage":
            if quota.max_storage_bytes != -1 and (
                quota.current_storage_bytes + amount
            ) > quota.max_storage_bytes:
                return (
                    False,
                    f"Storage limit reached. Please upgrade your plan for more storage.",
                )

        elif quota_type == "api_calls":
            if (
                quota.max_api_calls_per_month != -1
                and quota.current_api_calls_this_month >= quota.max_api_calls_per_month
            ):
                return (
                    False,
                    f"API call limit reached ({quota.max_api_calls_per_month}/month). Please upgrade your plan.",
                )

        elif quota_type == "file_uploads":
            if (
                quota.max_file_uploads_per_day != -1
                and quota.current_file_uploads_today >= quota.max_file_uploads_per_day
            ):
                return (
                    False,
                    f"Daily file upload limit reached ({quota.max_file_uploads_per_day}). Please upgrade your plan.",
                )

            # Also check file size limit
            if quota.max_file_size_bytes != -1 and amount > quota.max_file_size_bytes:
                max_size_mb = quota.max_file_size_bytes / (1024 * 1024)
                return (
                    False,
                    f"File size exceeds limit ({max_size_mb:.1f}MB). Please upgrade your plan for larger files.",
                )

        return True, None

    @staticmethod
    async def get_or_create_quota(
        db: AsyncSession, organization_id: uuid.UUID
    ) -> OrganizationQuota:
        """Get or create quota for an organization."""
        result = await db.execute(
            select(OrganizationQuota).where(
                OrganizationQuota.organization_id == organization_id
            )
        )
        quota = result.scalar_one_or_none()

        if not quota:
            quota = OrganizationQuota(organization_id=organization_id)
            db.add(quota)
            await db.commit()
            await db.refresh(quota)

        return quota

    @staticmethod
    async def check_and_reset_monthly_quotas(
        db: AsyncSession, quota: OrganizationQuota
    ) -> OrganizationQuota:
        """Reset monthly quotas if needed."""
        now = datetime.now(timezone.utc)
        # Reset if more than 30 days have passed
        if (now - quota.api_calls_reset_at).days >= 30:
            quota.current_api_calls_this_month = 0
            quota.api_calls_reset_at = now
            await db.commit()
            await db.refresh(quota)
        return quota

    @staticmethod
    async def check_and_reset_daily_quotas(
        db: AsyncSession, quota: OrganizationQuota
    ) -> OrganizationQuota:
        """Reset daily quotas if needed."""
        now = datetime.now(timezone.utc)
        # Reset if more than 1 day has passed
        if (now - quota.file_uploads_reset_at).days >= 1:
            quota.current_file_uploads_today = 0
            quota.file_uploads_reset_at = now
            await db.commit()
            await db.refresh(quota)
        return quota

    @staticmethod
    async def increment_api_calls(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Increment API call counter."""
        quota = await QuotaService.get_or_create_quota(db, organization_id)
        quota = await QuotaService.check_and_reset_monthly_quotas(db, quota)

        quota.current_api_calls_this_month += 1

        # Log usage
        log = UsageLog(
            organization_id=organization_id,
            user_id=user_id,
            usage_type="api_call",
            extra_data=metadata,
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def increment_file_uploads(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        file_size: int = 0,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Increment file upload counter and storage usage."""
        quota = await QuotaService.get_or_create_quota(db, organization_id)
        quota = await QuotaService.check_and_reset_daily_quotas(db, quota)

        quota.current_file_uploads_today += 1
        quota.current_storage_bytes += file_size

        # Log usage
        log = UsageLog(
            organization_id=organization_id,
            user_id=user_id,
            usage_type="file_upload",
            extra_data={**(metadata or {}), "file_size": file_size},
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def decrement_storage(
        db: AsyncSession,
        organization_id: uuid.UUID,
        file_size: int,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Decrement storage usage."""
        quota = await QuotaService.get_or_create_quota(db, organization_id)
        quota.current_storage_bytes = max(0, quota.current_storage_bytes - file_size)

        # Log usage
        log = UsageLog(
            organization_id=organization_id,
            user_id=user_id,
            usage_type="storage_remove",
            extra_data={**(metadata or {}), "file_size": file_size},
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def increment_users(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Increment user counter."""
        quota = await QuotaService.get_or_create_quota(db, organization_id)
        quota.current_users += 1

        # Log usage
        log = UsageLog(
            organization_id=organization_id,
            user_id=user_id,
            usage_type="user_add",
            extra_data=metadata,
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def decrement_users(
        db: AsyncSession,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Decrement user counter."""
        quota = await QuotaService.get_or_create_quota(db, organization_id)
        quota.current_users = max(0, quota.current_users - 1)

        # Log usage
        log = UsageLog(
            organization_id=organization_id,
            user_id=user_id,
            usage_type="user_remove",
            extra_data=metadata,
        )
        db.add(log)
        await db.commit()

    @staticmethod
    async def update_limits(
        db: AsyncSession,
        organization_id: uuid.UUID,
        **limits: Any
    ) -> OrganizationQuota:
        """Update quota limits for an organization."""
        quota = await QuotaService.get_or_create_quota(db, organization_id)

        for key, value in limits.items():
            if value is not None and hasattr(quota, key):
                setattr(quota, key, value)

        await db.commit()
        await db.refresh(quota)
        return quota

    @staticmethod
    async def get_usage_logs(
        db: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        usage_type: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[list[UsageLog], int]:
        """Get paginated usage logs for an organization."""
        query = select(UsageLog).where(UsageLog.organization_id == organization_id)

        if usage_type:
            query = query.where(UsageLog.usage_type == usage_type)
        if user_id:
            query = query.where(UsageLog.user_id == user_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(UsageLog.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        logs = list(result.scalars().all())

        return logs, total
