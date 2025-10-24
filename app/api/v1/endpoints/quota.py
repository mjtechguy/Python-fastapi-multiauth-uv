"""Quota management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.quota import (
    QuotaLimits,
    QuotaStatus,
    QuotaUsage,
    UpdateQuotaLimitsRequest,
    UpdateQuotaLimitsResponse,
    UsageLogEntry,
    UsageLogListResponse,
)
from app.services.quota import QuotaService

router = APIRouter(prefix="/quota", tags=["quota"])


@router.get("/status", response_model=QuotaStatus)
async def get_quota_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuotaStatus:
    """Get current quota status for user's organization."""
    # Get user's organization (users can only be in one org)
    from app.services.organization import OrganizationService

    orgs, _ = await OrganizationService.list_user_organizations(db, current_user.id, limit=1)

    if not orgs:
        raise HTTPException(status_code=400, detail="User does not belong to an organization")

    organization_id = orgs[0].id
    quota = await QuotaService.get_or_create_quota(db, organization_id)

    # Reset quotas if needed
    quota = await QuotaService.check_and_reset_monthly_quotas(db, quota)
    quota = await QuotaService.check_and_reset_daily_quotas(db, quota)

    return QuotaStatus(
        organization_id=quota.organization_id,
        limits=QuotaLimits(
            max_users=quota.max_users,
            max_storage_bytes=quota.max_storage_bytes,
            max_api_calls_per_month=quota.max_api_calls_per_month,
            max_file_uploads_per_day=quota.max_file_uploads_per_day,
            max_file_size_bytes=quota.max_file_size_bytes,
        ),
        usage=QuotaUsage(
            current_users=quota.current_users,
            current_storage_bytes=quota.current_storage_bytes,
            current_api_calls_this_month=quota.current_api_calls_this_month,
            current_file_uploads_today=quota.current_file_uploads_today,
        ),
        usage_percentages={
            "users": quota.get_usage_percentage("users"),
            "storage": quota.get_usage_percentage("storage"),
            "api_calls": quota.get_usage_percentage("api_calls"),
            "file_uploads": quota.get_usage_percentage("file_uploads"),
        },
        api_calls_reset_at=quota.api_calls_reset_at,
        file_uploads_reset_at=quota.file_uploads_reset_at,
        last_updated_at=quota.last_updated_at,
        created_at=quota.created_at,
    )


@router.put("/limits", response_model=UpdateQuotaLimitsResponse)
async def update_quota_limits(
    request: UpdateQuotaLimitsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UpdateQuotaLimitsResponse:
    """
    Update quota limits for user's organization.
    Requires admin/owner permissions.
    """
    # Get user's organization
    from app.services.organization import OrganizationService

    orgs, _ = await OrganizationService.list_user_organizations(db, current_user.id, limit=1)

    if not orgs:
        raise HTTPException(status_code=400, detail="User does not belong to an organization")

    # TODO: Add permission check - only org admins/owners should be able to update quotas
    # For now, allowing any authenticated user

    organization_id = orgs[0].id

    # Update limits
    await QuotaService.update_limits(
        db,
        organization_id,
        max_users=request.max_users,
        max_storage_bytes=request.max_storage_bytes,
        max_api_calls_per_month=request.max_api_calls_per_month,
        max_file_uploads_per_day=request.max_file_uploads_per_day,
        max_file_size_bytes=request.max_file_size_bytes,
    )

    status = await get_quota_status(current_user, db)

    return UpdateQuotaLimitsResponse(
        message="Quota limits updated successfully",
        quota=status,
    )


@router.get("/usage-logs", response_model=UsageLogListResponse)
async def get_usage_logs(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    usage_type: str | None = Query(None, description="Filter by usage type"),
    user_id: uuid.UUID | None = Query(None, description="Filter by user ID"),
) -> UsageLogListResponse:
    """Get usage logs for user's organization."""
    # Get user's organization (users can only be in one org)
    from app.services.organization import OrganizationService

    orgs, _ = await OrganizationService.list_user_organizations(db, current_user.id, limit=1)

    if not orgs:
        raise HTTPException(status_code=400, detail="User does not belong to an organization")

    organization_id = orgs[0].id

    logs, total = await QuotaService.get_usage_logs(
        db,
        organization_id,
        page=page,
        page_size=page_size,
        usage_type=usage_type,
        user_id=user_id,
    )

    return UsageLogListResponse(
        logs=[
            UsageLogEntry(
                id=log.id,
                organization_id=log.organization_id,
                user_id=log.user_id,
                usage_type=log.usage_type,
                metadata=log.extra_data,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
