"""End-to-end tests for audit log management."""

from datetime import datetime
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit_log_service import AuditLogService
from app.services.user import UserService


class TestAuditLogCreation:
    """Test audit log creation via service."""

    async def test_create_audit_log(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test creating an audit log entry."""
        audit_log = await AuditLogService.create_audit_log(
            db=db_session,
            action="user.profile.update",
            status="success",
            user_id=test_user.id,
            resource_type="user",
            resource_id=str(test_user.id),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            extra_data={"field": "email", "old_value": "old@example.com"},
        )

        assert audit_log.id is not None
        assert audit_log.action == "user.profile.update"
        assert audit_log.status == "success"
        assert audit_log.user_id == test_user.id
        assert audit_log.ip_address == "192.168.1.1"

        # Verify in database
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.id == audit_log.id)
        )
        db_log = result.scalar_one_or_none()
        assert db_log is not None

    async def test_create_audit_log_without_user(
        self,
        db_session: AsyncSession,
    ):
        """Test creating system audit log without user."""
        audit_log = await AuditLogService.create_audit_log(
            db=db_session,
            action="system.cleanup.completed",
            status="success",
            extra_data={"records_deleted": 100},
        )

        assert audit_log.user_id is None
        assert audit_log.action == "system.cleanup.completed"


class TestAuditLogListing:
    """Test listing audit logs."""

    async def test_list_my_audit_logs(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing current user's audit logs."""
        # Create some audit logs
        for i in range(3):
            await AuditLogService.create_audit_log(
                db=db_session,
                action=f"user.action.{i}",
                status="success",
                user_id=test_user.id,
            )

        response = await authenticated_client.get("/api/v1/audit-logs/me")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3
        assert len(data["items"]) >= 3

        # Verify all logs belong to current user
        for log in data["items"]:
            assert log["user_id"] == str(test_user.id)

    async def test_list_audit_logs_pagination(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test audit log pagination."""
        # Create multiple logs
        for i in range(10):
            await AuditLogService.create_audit_log(
                db=db_session,
                action=f"user.test.{i}",
                status="success",
                user_id=test_user.id,
            )

        # Get first page
        response = await authenticated_client.get(
            "/api/v1/audit-logs/me?page=1&page_size=5"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 5
        assert len(data["items"]) == 5
        assert data["pages"] >= 2

    async def test_list_audit_logs_with_filters(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering audit logs."""
        # Create logs with different actions
        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.login",
            status="success",
            user_id=test_user.id,
        )
        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.logout",
            status="success",
            user_id=test_user.id,
        )

        # Filter by action
        response = await authenticated_client.get(
            "/api/v1/audit-logs/me?action=user.login"
        )

        assert response.status_code == 200
        data = response.json()

        assert all(log["action"] == "user.login" for log in data["items"])

    async def test_non_superuser_cannot_view_all_logs(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that non-superusers cannot view other users' logs."""
        # Create another user
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        # Create log for other user
        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.test",
            status="success",
            user_id=other_user.id,
        )

        # Try to filter by other user's ID
        response = await authenticated_client.get(
            f"/api/v1/audit-logs?user_id={other_user.id}"
        )

        assert response.status_code == 403

    async def test_superuser_can_view_all_logs(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that superusers can view all audit logs."""
        # Make test_user a superuser
        test_user.is_superuser = True
        await db_session.commit()

        # Create another user
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        # Create log for other user
        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.test",
            status="success",
            user_id=other_user.id,
        )

        # View all logs
        response = await authenticated_client.get("/api/v1/audit-logs")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0


class TestAuditLogRetrieval:
    """Test retrieving individual audit logs."""

    async def test_get_audit_log(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting specific audit log."""
        audit_log = await AuditLogService.create_audit_log(
            db=db_session,
            action="user.profile.view",
            status="success",
            user_id=test_user.id,
        )

        response = await authenticated_client.get(
            f"/api/v1/audit-logs/{audit_log.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(audit_log.id)
        assert data["action"] == "user.profile.view"

    async def test_get_nonexistent_audit_log(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test getting non-existent audit log."""

        fake_id = uuid4()
        response = await authenticated_client.get(
            f"/api/v1/audit-logs/{fake_id}"
        )

        assert response.status_code == 404

    async def test_cannot_view_other_user_audit_log(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that users cannot view other users' audit logs."""
        # Create another user
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        # Create log for other user
        audit_log = await AuditLogService.create_audit_log(
            db=db_session,
            action="user.test",
            status="success",
            user_id=other_user.id,
        )

        response = await authenticated_client.get(
            f"/api/v1/audit-logs/{audit_log.id}"
        )

        assert response.status_code == 403


class TestLoginHistory:
    """Test login history tracking."""

    async def test_get_login_history(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting login history."""
        # Create successful login logs
        for i in range(3):
            await AuditLogService.create_audit_log(
                db=db_session,
                action="user.login",
                status="success",
                user_id=test_user.id,
                ip_address=f"192.168.1.{i}",
            )

        response = await authenticated_client.get(
            "/api/v1/audit-logs/me/login-history?limit=10"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 3
        assert all(log["action"] == "user.login" for log in data["items"])
        assert all(log["status"] == "success" for log in data["items"])

    async def test_get_failed_login_attempts(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting failed login attempts."""
        # Create failed login logs
        for _i in range(5):
            await AuditLogService.create_audit_log(
                db=db_session,
                action="user.login",
                status="failure",
                user_id=test_user.id,
                ip_address="192.168.1.100",
                extra_data={"reason": "invalid_password"},
            )

        response = await authenticated_client.get(
            f"/api/v1/audit-logs/users/{test_user.id}/failed-logins?hours=24"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 5
        assert all(log["status"] == "failure" for log in data["items"])

    async def test_cannot_view_other_user_failed_logins(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that users cannot view other users' failed login attempts."""
        # Create another user
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        response = await authenticated_client.get(
            f"/api/v1/audit-logs/users/{other_user.id}/failed-logins"
        )

        assert response.status_code == 403


class TestResourceAuditLogs:
    """Test resource-specific audit logs."""

    async def test_list_resource_audit_logs(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing audit logs for a specific resource."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        resource_id = "test-resource-123"

        # Create logs for resource
        for action in ["create", "update", "delete"]:
            await AuditLogService.create_audit_log(
                db=db_session,
                action=f"file.{action}",
                status="success",
                user_id=test_user.id,
                resource_type="file",
                resource_id=resource_id,
            )

        response = await authenticated_client.get(
            f"/api/v1/audit-logs/resource/file/{resource_id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 3
        assert all(log["resource_id"] == resource_id for log in data["items"])

    async def test_resource_logs_require_superuser(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that viewing resource logs requires superuser."""
        response = await authenticated_client.get(
            "/api/v1/audit-logs/resource/file/test-123"
        )

        assert response.status_code == 403


class TestAuditLogSearch:
    """Test searching audit logs."""

    async def test_search_audit_logs(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test searching audit logs."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        # Create logs with different actions
        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.login",
            status="success",
            user_id=test_user.id,
        )
        await AuditLogService.create_audit_log(
            db=db_session,
            action="organization.create",
            status="success",
            user_id=test_user.id,
        )

        # Search for "login"
        response = await authenticated_client.get(
            "/api/v1/audit-logs/search?q=login"
        )

        assert response.status_code == 200
        data = response.json()

        assert all("login" in log["action"].lower() for log in data["items"])

    async def test_search_requires_superuser(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that searching requires superuser."""
        response = await authenticated_client.get(
            "/api/v1/audit-logs/search?q=test"
        )

        assert response.status_code == 403


class TestAuditLogStatistics:
    """Test audit log statistics."""

    async def test_get_statistics(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting audit log statistics."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        # Create logs with different statuses
        await AuditLogService.create_audit_log(
            db=db_session,
            action="test.success",
            status="success",
            user_id=test_user.id,
        )
        await AuditLogService.create_audit_log(
            db=db_session,
            action="test.failure",
            status="failure",
            user_id=test_user.id,
        )
        await AuditLogService.create_audit_log(
            db=db_session,
            action="test.error",
            status="error",
            user_id=test_user.id,
        )

        response = await authenticated_client.get(
            "/api/v1/audit-logs/statistics"
        )

        assert response.status_code == 200
        data = response.json()

        assert "total" in data
        assert "by_status" in data
        assert "unique_users" in data
        assert data["by_status"]["success"] >= 1
        assert data["by_status"]["failure"] >= 1
        assert data["by_status"]["error"] >= 1

    async def test_statistics_require_superuser(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that statistics require superuser."""
        response = await authenticated_client.get(
            "/api/v1/audit-logs/statistics"
        )

        assert response.status_code == 403


class TestAuditLogFiltering:
    """Test advanced filtering of audit logs."""

    async def test_filter_by_status(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering by status."""
        # Create logs with different statuses
        await AuditLogService.create_audit_log(
            db=db_session,
            action="test.action",
            status="success",
            user_id=test_user.id,
        )
        await AuditLogService.create_audit_log(
            db=db_session,
            action="test.action",
            status="failure",
            user_id=test_user.id,
        )

        # Filter by success
        response = await authenticated_client.get(
            "/api/v1/audit-logs/me?status=success"
        )

        assert response.status_code == 200
        data = response.json()

        assert all(log["status"] == "success" for log in data["items"])

    async def test_filter_by_resource_type(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering by resource type."""
        # Create logs with different resource types
        await AuditLogService.create_audit_log(
            db=db_session,
            action="file.upload",
            status="success",
            user_id=test_user.id,
            resource_type="file",
        )
        await AuditLogService.create_audit_log(
            db=db_session,
            action="org.create",
            status="success",
            user_id=test_user.id,
            resource_type="organization",
        )

        # Filter by file
        response = await authenticated_client.get(
            "/api/v1/audit-logs/me?resource_type=file"
        )

        assert response.status_code == 200
        data = response.json()

        assert all(log["resource_type"] == "file" for log in data["items"])


class TestAuditLogAuthorization:
    """Test audit log authorization and permissions."""

    async def test_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Test that audit logs require authentication."""
        response = await client.get("/api/v1/audit-logs/me")
        assert response.status_code == 401

    async def test_user_can_view_own_logs(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that users can view their own logs."""
        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.test",
            status="success",
            user_id=test_user.id,
        )

        response = await authenticated_client.get("/api/v1/audit-logs/me")
        assert response.status_code == 200

    async def test_user_cannot_view_others_logs(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that users cannot view other users' logs directly."""
        # Create another user
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        await AuditLogService.create_audit_log(
            db=db_session,
            action="user.test",
            status="success",
            user_id=other_user.id,
        )

        # Try to access with user_id filter
        response = await authenticated_client.get(
            f"/api/v1/audit-logs?user_id={other_user.id}"
        )
        assert response.status_code == 403


class TestAuditLogServiceMethods:
    """Test audit log service methods."""

    async def test_get_recent_failed_logins(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting recent failed logins."""
        # Create failed login attempts
        for _i in range(3):
            await AuditLogService.create_audit_log(
                db=db_session,
                action="user.login",
                status="failure",
                user_id=test_user.id,
            )

        failed_logins = await AuditLogService.get_recent_failed_logins(
            db_session,
            test_user.id,
            hours=24,
        )

        assert len(failed_logins) >= 3

    async def test_get_login_history(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting login history."""
        # Create successful logins
        for _i in range(5):
            await AuditLogService.create_audit_log(
                db=db_session,
                action="user.login",
                status="success",
                user_id=test_user.id,
            )

        history = await AuditLogService.get_login_history(
            db_session,
            test_user.id,
            limit=10,
        )

        assert len(history) >= 5

    async def test_log_user_action(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test convenience method for logging user action."""
        audit_log = await AuditLogService.log_user_action(
            db=db_session,
            user_id=test_user.id,
            action="user.profile.update",
            status="success",
            resource_type="user",
            resource_id=str(test_user.id),
        )

        assert audit_log.user_id == test_user.id
        assert audit_log.action == "user.profile.update"
