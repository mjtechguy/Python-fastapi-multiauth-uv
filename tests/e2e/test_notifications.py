"""End-to-end tests for notification management."""

from datetime import datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.user import UserService


class TestNotificationCreation:
    """Test notification creation."""

    async def test_create_notification(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test creating a new notification."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "info",
                "title": "Test Notification",
                "message": "This is a test notification",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["type"] == "info"
        assert data["title"] == "Test Notification"
        assert data["message"] == "This is a test notification"
        assert data["user_id"] == str(test_user.id)
        assert data["is_read"] is False
        assert data["read_at"] is None

        # Verify in database
        result = await db_session.execute(
            select(Notification).where(Notification.user_id == test_user.id)
        )
        notification = result.scalar_one_or_none()
        assert notification is not None

    async def test_create_notification_with_action(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test creating notification with action button."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "success",
                "title": "Action Required",
                "message": "Please complete your profile",
                "action_url": "/profile",
                "action_label": "Go to Profile",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["action_url"] == "/profile"
        assert data["action_label"] == "Go to Profile"

    async def test_create_notification_with_extra_data(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test creating notification with extra data."""
        extra_data = {"order_id": "12345", "amount": 99.99}

        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "warning",
                "title": "Order Update",
                "message": "Your order has shipped",
                "extra_data": extra_data,
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["extra_data"] == extra_data

    async def test_create_notification_requires_auth(
        self,
        client: AsyncClient,
    ):
        """Test that creating notifications requires authentication."""
        response = await client.post(
            "/api/v1/notifications",
            json={"type": "info", "title": "Test", "message": "Test"},
        )

        assert response.status_code == 401

    async def test_create_notification_invalid_type(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that invalid notification types are rejected."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "invalid_type",
                "title": "Test",
                "message": "Test",
            },
        )

        assert response.status_code == 422  # Validation error


class TestNotificationListing:
    """Test listing notifications."""

    async def test_list_notifications(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing user notifications."""
        # Create some notifications
        for i in range(3):
            await NotificationService.create_notification(
                db_session,
                test_user.id,
                "info",
                f"Notification {i}",
                f"Message {i}",
            )

        response = await authenticated_client.get("/api/v1/notifications")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert "unread_count" in data
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

    async def test_list_notifications_pagination(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test notification pagination."""
        # Create 10 notifications
        for i in range(10):
            await NotificationService.create_notification(
                db_session,
                test_user.id,
                "info",
                f"Notification {i}",
                f"Message {i}",
            )

        # Get first page
        response = await authenticated_client.get(
            "/api/v1/notifications?page=1&page_size=5"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["items"]) == 5
        assert data["pages"] >= 2

    async def test_list_unread_only(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing only unread notifications."""
        # Create unread notification
        await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Unread Notification",
            "Unread message",
        )

        # Create read notification
        read_notif = await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Read Notification",
            "Read message",
        )
        await NotificationService.mark_as_read(db_session, read_notif.id, test_user.id)

        # List all
        response_all = await authenticated_client.get("/api/v1/notifications")
        assert response_all.status_code == 200
        all_data = response_all.json()

        # List unread only
        response_unread = await authenticated_client.get(
            "/api/v1/notifications?unread_only=true"
        )
        assert response_unread.status_code == 200
        unread_data = response_unread.json()

        assert unread_data["total"] < all_data["total"]
        assert all(not item["is_read"] for item in unread_data["items"])


class TestNotificationRetrieval:
    """Test retrieving individual notifications."""

    async def test_get_notification(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting specific notification."""
        notification = await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Test Notification",
            "Test message",
        )

        response = await authenticated_client.get(
            f"/api/v1/notifications/{notification.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(notification.id)
        assert data["title"] == "Test Notification"

    async def test_get_nonexistent_notification(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test getting non-existent notification."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.get(
            f"/api/v1/notifications/{fake_id}"
        )

        assert response.status_code == 404

    async def test_cannot_get_other_user_notification(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that users cannot access other users' notifications."""
        # Create another user
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        # Create notification for other user
        notification = await NotificationService.create_notification(
            db_session,
            other_user.id,
            "info",
            "Other's Notification",
            "Other's message",
        )

        response = await authenticated_client.get(
            f"/api/v1/notifications/{notification.id}"
        )

        assert response.status_code == 404


class TestNotificationMarkAsRead:
    """Test marking notifications as read."""

    async def test_mark_notification_as_read(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test marking a notification as read."""
        notification = await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Test Notification",
            "Test message",
        )

        assert notification.is_read is False
        assert notification.read_at is None

        response = await authenticated_client.patch(
            f"/api/v1/notifications/{notification.id}/read"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_read"] is True
        assert data["read_at"] is not None

        # Verify in database
        await db_session.refresh(notification)
        assert notification.is_read is True
        assert notification.read_at is not None

    async def test_mark_nonexistent_notification_as_read(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test marking non-existent notification as read."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.patch(
            f"/api/v1/notifications/{fake_id}/read"
        )

        assert response.status_code == 404

    async def test_mark_all_as_read(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test marking all notifications as read."""
        # Create unread notifications
        for i in range(5):
            await NotificationService.create_notification(
                db_session,
                test_user.id,
                "info",
                f"Notification {i}",
                f"Message {i}",
            )

        response = await authenticated_client.post(
            "/api/v1/notifications/mark-all-read"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["count"] >= 5
        assert "Marked" in data["message"]

        # Verify all are read
        result = await db_session.execute(
            select(Notification).where(
                Notification.user_id == test_user.id,
                not Notification.is_read,
            )
        )
        unread_notifications = result.scalars().all()
        assert len(unread_notifications) == 0


class TestNotificationUnreadCount:
    """Test unread notification count."""

    async def test_get_unread_count(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting unread notification count."""
        # Create unread notifications
        for i in range(3):
            await NotificationService.create_notification(
                db_session,
                test_user.id,
                "info",
                f"Unread {i}",
                f"Message {i}",
            )

        # Create read notification
        read_notif = await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Read Notification",
            "Read message",
        )
        await NotificationService.mark_as_read(db_session, read_notif.id, test_user.id)

        response = await authenticated_client.get(
            "/api/v1/notifications/unread-count"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["unread_count"] >= 3


class TestNotificationDeletion:
    """Test notification deletion."""

    async def test_delete_notification(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test deleting a notification."""
        notification = await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Test Notification",
            "Test message",
        )
        notification_id = notification.id

        response = await authenticated_client.delete(
            f"/api/v1/notifications/{notification_id}"
        )

        assert response.status_code == 204

        # Verify deleted
        result = await db_session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_nonexistent_notification(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test deleting non-existent notification."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.delete(
            f"/api/v1/notifications/{fake_id}"
        )

        assert response.status_code == 404

    async def test_delete_read_notifications(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test deleting all read notifications."""
        # Create and mark as read
        for i in range(3):
            notif = await NotificationService.create_notification(
                db_session,
                test_user.id,
                "info",
                f"Read {i}",
                f"Message {i}",
            )
            await NotificationService.mark_as_read(db_session, notif.id, test_user.id)

        # Create unread notification
        unread = await NotificationService.create_notification(
            db_session,
            test_user.id,
            "info",
            "Unread",
            "Unread message",
        )

        response = await authenticated_client.delete(
            "/api/v1/notifications/read/all"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["count"] >= 3
        assert "Deleted" in data["message"]

        # Verify unread notification still exists
        await db_session.refresh(unread)
        assert unread is not None


class TestNotificationBroadcast:
    """Test broadcasting notifications."""

    async def test_broadcast_notification(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test broadcasting notification to multiple users."""
        # Create additional users
        user2 = await UserService.create_user(
            db_session,
            email=f"user2_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="User 2",
        )
        user3 = await UserService.create_user(
            db_session,
            email=f"user3_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="User 3",
        )

        # Make test_user superuser
        test_user.is_superuser = True
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/v1/notifications/broadcast",
            json={
                "user_ids": [
                    str(test_user.id),
                    str(user2.id),
                    str(user3.id),
                ],
                "type": "info",
                "title": "System Announcement",
                "message": "This is a broadcast message",
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["notifications_created"] == 3
        assert "Successfully sent" in data["message"]

        # Verify notifications created
        for user_id in [test_user.id, user2.id, user3.id]:
            result = await db_session.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.title == "System Announcement",
                )
            )
            notif = result.scalar_one_or_none()
            assert notif is not None

    async def test_broadcast_requires_superuser(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
    ):
        """Test that broadcasting requires superuser permissions."""
        # Ensure user is not superuser
        response = await authenticated_client.post(
            "/api/v1/notifications/broadcast",
            json={
                "user_ids": [str(test_user.id)],
                "type": "info",
                "title": "Test",
                "message": "Test",
            },
        )

        assert response.status_code == 403
        assert "administrator" in response.json()["detail"].lower()


class TestNotificationTypes:
    """Test different notification types."""

    async def test_info_notification(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test info type notification."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "info",
                "title": "Information",
                "message": "This is informational",
            },
        )

        assert response.status_code == 201
        assert response.json()["type"] == "info"

    async def test_success_notification(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test success type notification."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "success",
                "title": "Success",
                "message": "Operation succeeded",
            },
        )

        assert response.status_code == 201
        assert response.json()["type"] == "success"

    async def test_warning_notification(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test warning type notification."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "warning",
                "title": "Warning",
                "message": "This is a warning",
            },
        )

        assert response.status_code == 201
        assert response.json()["type"] == "warning"

    async def test_error_notification(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test error type notification."""
        response = await authenticated_client.post(
            "/api/v1/notifications",
            json={
                "type": "error",
                "title": "Error",
                "message": "An error occurred",
            },
        )

        assert response.status_code == 201
        assert response.json()["type"] == "error"
