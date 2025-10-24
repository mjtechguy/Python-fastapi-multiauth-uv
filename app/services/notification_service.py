"""Notification service for in-app notifications."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User

NotificationType = Literal["info", "success", "warning", "error"]


class NotificationService:
    """Service for managing user notifications."""

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        action_url: str | None = None,
        action_label: str | None = None,
        extra_data: dict | None = None,
    ) -> Notification:
        """Create a new notification for a user.

        Args:
            db: Database session
            user_id: ID of the user to notify
            notification_type: Notification type (info, success, warning, error)
            title: Notification title
            message: Notification message
            action_url: Optional URL for action button
            action_label: Optional label for action button
            extra_data: Optional additional data as JSON

        Returns:
            Created notification

        Raises:
            ValueError: If user doesn't exist or validation fails
        """
        # Verify user exists
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        # Validate type
        valid_types = ["info", "success", "warning", "error"]
        if notification_type not in valid_types:
            raise ValueError(
                f"Invalid notification type. Must be one of: {', '.join(valid_types)}"
            )

        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            action_url=action_url,
            action_label=action_label,
            extra_data=extra_data or {},
        )

        db.add(notification)
        await db.flush()
        await db.refresh(notification)

        return notification

    @staticmethod
    async def get_notification_by_id(
        db: AsyncSession, notification_id: UUID, user_id: UUID | None = None
    ) -> Notification | None:
        """Get notification by ID.

        Args:
            db: Database session
            notification_id: Notification ID
            user_id: Optional user ID to verify ownership

        Returns:
            Notification if found and authorized, None otherwise
        """
        conditions = [Notification.id == notification_id]
        if user_id:
            conditions.append(Notification.user_id == user_id)

        result = await db.execute(select(Notification).where(and_(*conditions)))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_user_notifications(
        db: AsyncSession,
        user_id: UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Notification], int]:
        """List notifications for a user.

        Args:
            db: Database session
            user_id: User ID
            unread_only: Only return unread notifications (default: False)
            skip: Offset for pagination
            limit: Limit for pagination

        Returns:
            Tuple of (notifications list, total count)
        """
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read is False)

        # Get total count
        count_result = await db.execute(
            select(func.count(Notification.id)).where(and_(*conditions))
        )
        total = count_result.scalar_one()

        # Get notifications
        result = await db.execute(
            select(Notification)
            .where(and_(*conditions))
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        notifications = list(result.scalars().all())

        return notifications, total

    @staticmethod
    async def mark_as_read(
        db: AsyncSession, notification_id: UUID, user_id: UUID
    ) -> Notification:
        """Mark a notification as read.

        Args:
            db: Database session
            notification_id: Notification ID
            user_id: User ID (for authorization)

        Returns:
            Updated notification

        Raises:
            ValueError: If notification not found or not authorized
        """
        notification = await NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )

        if not notification:
            raise ValueError("Notification not found")

        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await db.flush()
            await db.refresh(notification)

        return notification

    @staticmethod
    async def mark_all_as_read(db: AsyncSession, user_id: UUID) -> int:
        """Mark all notifications as read for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of notifications marked as read
        """
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read is False,
                )
            )
        )
        notifications = result.scalars().all()

        count = 0
        now = datetime.now(UTC)
        for notification in notifications:
            notification.is_read = True
            notification.read_at = now
            count += 1

        await db.flush()

        return count

    @staticmethod
    async def delete_notification(
        db: AsyncSession, notification_id: UUID, user_id: UUID
    ) -> bool:
        """Delete a notification.

        Args:
            db: Database session
            notification_id: Notification ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        notification = await NotificationService.get_notification_by_id(
            db, notification_id, user_id
        )

        if not notification:
            return False

        await db.delete(notification)
        await db.flush()

        return True

    @staticmethod
    async def delete_read_notifications(db: AsyncSession, user_id: UUID) -> int:
        """Delete all read notifications for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of notifications deleted
        """
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read is True,
                )
            )
        )
        notifications = result.scalars().all()

        count = len(notifications)

        for notification in notifications:
            await db.delete(notification)

        await db.flush()

        return count

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
        """Get count of unread notifications for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Count of unread notifications
        """
        result = await db.execute(
            select(func.count(Notification.id)).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read is False,
                )
            )
        )
        return result.scalar_one()

    @staticmethod
    async def cleanup_old_notifications(
        db: AsyncSession, days_old: int = 90
    ) -> int:
        """Delete old read notifications.

        Args:
            db: Database session
            days_old: Delete notifications older than this many days (default: 90)

        Returns:
            Number of notifications deleted
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days_old)

        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.is_read is True,
                    Notification.created_at < cutoff_date,
                )
            )
        )
        notifications = result.scalars().all()

        count = len(notifications)

        for notification in notifications:
            await db.delete(notification)

        await db.flush()

        return count

    @staticmethod
    async def broadcast_to_users(
        db: AsyncSession,
        user_ids: list[UUID],
        notification_type: NotificationType,
        title: str,
        message: str,
        action_url: str | None = None,
        action_label: str | None = None,
        extra_data: dict | None = None,
    ) -> list[Notification]:
        """Create the same notification for multiple users.

        Args:
            db: Database session
            user_ids: List of user IDs to notify
            notification_type: Notification type
            title: Notification title
            message: Notification message
            action_url: Optional URL for action button
            action_label: Optional label for action button
            extra_data: Optional additional data

        Returns:
            List of created notifications
        """
        notifications = []

        for user_id in user_ids:
            try:
                notification = await NotificationService.create_notification(
                    db=db,
                    user_id=user_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    action_url=action_url,
                    action_label=action_label,
                    extra_data=extra_data,
                )
                notifications.append(notification)
            except ValueError:
                # Skip users that don't exist
                continue

        return notifications
