"""Audit log service for security and compliance tracking."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

AuditStatus = Literal["success", "failure", "error"]


class AuditLogService:
    """Service for managing audit logs."""

    @staticmethod
    async def create_audit_log(
        db: AsyncSession,
        action: str,
        status: AuditStatus,
        user_id: UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        extra_data: dict | None = None,
    ) -> AuditLog:
        """Create a new audit log entry.

        Args:
            db: Database session
            action: Action performed (e.g., 'user.login', 'organization.create')
            status: Result of the action (success, failure, error)
            user_id: Optional ID of user who performed the action
            resource_type: Optional type of resource affected (e.g., 'user', 'organization')
            resource_id: Optional ID of the affected resource
            ip_address: Optional IP address of the request
            user_agent: Optional user agent string
            extra_data: Optional additional context data

        Returns:
            Created audit log entry
        """
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=extra_data or {},
            status=status,
        )

        db.add(audit_log)
        await db.flush()
        await db.refresh(audit_log)

        return audit_log

    @staticmethod
    async def get_audit_log_by_id(
        db: AsyncSession, audit_log_id: UUID
    ) -> AuditLog | None:
        """Get audit log by ID.

        Args:
            db: Database session
            audit_log_id: Audit log ID

        Returns:
            Audit log if found, None otherwise
        """
        result = await db.execute(
            select(AuditLog).where(AuditLog.id == audit_log_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_audit_logs(
        db: AsyncSession,
        user_id: UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: AuditStatus | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs with optional filters.

        Args:
            db: Database session
            user_id: Filter by user ID
            action: Filter by action
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            status: Filter by status
            start_date: Filter by date range start
            end_date: Filter by date range end
            skip: Offset for pagination
            limit: Limit for pagination

        Returns:
            Tuple of (audit logs list, total count)
        """
        conditions = []

        if user_id:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)
        if resource_type:
            conditions.append(AuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(AuditLog.resource_id == resource_id)
        if status:
            conditions.append(AuditLog.status == status)
        if start_date:
            conditions.append(AuditLog.created_at >= start_date)
        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        # Build base query
        where_clause = and_(*conditions) if conditions else True

        # Get total count
        count_result = await db.execute(
            select(func.count(AuditLog.id)).where(where_clause)
        )
        total = count_result.scalar_one()

        # Get audit logs
        result = await db.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        audit_logs = list(result.scalars().all())

        return audit_logs, total

    @staticmethod
    async def list_user_audit_logs(
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs for a specific user.

        Args:
            db: Database session
            user_id: User ID
            skip: Offset for pagination
            limit: Limit for pagination

        Returns:
            Tuple of (audit logs list, total count)
        """
        return await AuditLogService.list_audit_logs(
            db=db,
            user_id=user_id,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def list_resource_audit_logs(
        db: AsyncSession,
        resource_type: str,
        resource_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs for a specific resource.

        Args:
            db: Database session
            resource_type: Type of resource
            resource_id: ID of resource
            skip: Offset for pagination
            limit: Limit for pagination

        Returns:
            Tuple of (audit logs list, total count)
        """
        return await AuditLogService.list_audit_logs(
            db=db,
            resource_type=resource_type,
            resource_id=resource_id,
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def get_recent_failed_logins(
        db: AsyncSession,
        user_id: UUID,
        hours: int = 24,
    ) -> list[AuditLog]:
        """Get recent failed login attempts for a user.

        Useful for detecting brute force attacks.

        Args:
            db: Database session
            user_id: User ID
            hours: Look back period in hours (default: 24)

        Returns:
            List of failed login audit logs
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        result = await db.execute(
            select(AuditLog).where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.action.in_(["user.login", "auth.login"]),
                    AuditLog.status == "failure",
                    AuditLog.created_at >= cutoff_time,
                )
            ).order_by(AuditLog.created_at.desc())
        )

        return list(result.scalars().all())

    @staticmethod
    async def get_login_history(
        db: AsyncSession,
        user_id: UUID,
        limit: int = 10,
    ) -> list[AuditLog]:
        """Get recent successful login history for a user.

        Args:
            db: Database session
            user_id: User ID
            limit: Number of records to return (default: 10)

        Returns:
            List of successful login audit logs
        """
        result = await db.execute(
            select(AuditLog)
            .where(
                and_(
                    AuditLog.user_id == user_id,
                    AuditLog.action.in_(["user.login", "auth.login"]),
                    AuditLog.status == "success",
                )
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )

        return list(result.scalars().all())

    @staticmethod
    async def search_audit_logs(
        db: AsyncSession,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """Search audit logs by action or resource type.

        Args:
            db: Database session
            search_term: Term to search for in action or resource_type
            skip: Offset for pagination
            limit: Limit for pagination

        Returns:
            Tuple of (audit logs list, total count)
        """
        search_pattern = f"%{search_term}%"

        # Get total count
        count_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                or_(
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.resource_type.ilike(search_pattern),
                )
            )
        )
        total = count_result.scalar_one()

        # Get audit logs
        result = await db.execute(
            select(AuditLog)
            .where(
                or_(
                    AuditLog.action.ilike(search_pattern),
                    AuditLog.resource_type.ilike(search_pattern),
                )
            )
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        audit_logs = list(result.scalars().all())

        return audit_logs, total

    @staticmethod
    async def get_statistics(
        db: AsyncSession,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict:
        """Get audit log statistics.

        Args:
            db: Database session
            start_date: Optional start date for stats
            end_date: Optional end date for stats

        Returns:
            Dictionary with statistics
        """
        conditions = []
        if start_date:
            conditions.append(AuditLog.created_at >= start_date)
        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        where_clause = and_(*conditions) if conditions else True

        # Total logs
        total_result = await db.execute(
            select(func.count(AuditLog.id)).where(where_clause)
        )
        total = total_result.scalar_one()

        # By status
        success_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(where_clause, AuditLog.status == "success")
            )
        )
        success_count = success_result.scalar_one()

        failure_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(where_clause, AuditLog.status == "failure")
            )
        )
        failure_count = failure_result.scalar_one()

        error_result = await db.execute(
            select(func.count(AuditLog.id)).where(
                and_(where_clause, AuditLog.status == "error")
            )
        )
        error_count = error_result.scalar_one()

        # Unique users
        unique_users_result = await db.execute(
            select(func.count(func.distinct(AuditLog.user_id))).where(
                and_(where_clause, AuditLog.user_id.isnot(None))
            )
        )
        unique_users = unique_users_result.scalar_one()

        return {
            "total": total,
            "by_status": {
                "success": success_count,
                "failure": failure_count,
                "error": error_count,
            },
            "unique_users": unique_users,
        }

    @staticmethod
    async def cleanup_old_logs(
        db: AsyncSession,
        days_old: int = 180,
    ) -> int:
        """Delete old audit logs.

        Note: Consider data retention policies before using this.

        Args:
            db: Database session
            days_old: Delete logs older than this many days (default: 180)

        Returns:
            Number of logs deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)

        result = await db.execute(
            select(AuditLog).where(AuditLog.created_at < cutoff_date)
        )
        old_logs = result.scalars().all()

        count = len(old_logs)

        for log in old_logs:
            await db.delete(log)

        await db.flush()

        return count

    @staticmethod
    async def log_user_action(
        db: AsyncSession,
        user_id: UUID,
        action: str,
        status: AuditStatus = "success",
        resource_type: str | None = None,
        resource_id: str | None = None,
        extra_data: dict | None = None,
    ) -> AuditLog:
        """Convenience method to log a user action.

        Args:
            db: Database session
            user_id: User performing the action
            action: Action performed
            status: Result of action (default: success)
            resource_type: Optional resource type
            resource_id: Optional resource ID
            extra_data: Optional additional data

        Returns:
            Created audit log
        """
        return await AuditLogService.create_audit_log(
            db=db,
            action=action,
            status=status,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            extra_data=extra_data,
        )
