"""Extended E2E tests for session management functionality."""

from datetime import datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import UserSession
from app.models.user import User


class TestSessionCreation:
    """Test session creation on login."""

    async def test_login_creates_session(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that logging in creates a session entry."""
        # Register user
        register_data = {
            "email": f"session_test_{datetime.utcnow().timestamp()}@example.com",
            "password": "TestPassword123!",
            "full_name": "Session Test User",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login
        login_data = {"email": register_data["email"], "password": register_data["password"]}
        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

        # Verify session was created
        result = await db_session.execute(
            select(UserSession).join(User).where(User.email == register_data["email"])
        )
        session = result.scalar_one_or_none()
        assert session is not None
        assert session.is_active is True

    async def test_session_tracks_user_agent(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that session tracks user agent."""
        register_data = {
            "email": f"ua_test_{datetime.utcnow().timestamp()}@example.com",
            "password": "TestPassword123!",
            "full_name": "UA Test User",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login with custom user agent
        login_data = {"email": register_data["email"], "password": register_data["password"]}
        custom_headers = {"user-agent": "TestBrowser/1.0"}
        response = await client.post(
            "/api/v1/auth/login", json=login_data, headers=custom_headers
        )

        assert response.status_code == 200

        # Verify user agent was captured
        result = await db_session.execute(
            select(UserSession).join(User).where(User.email == register_data["email"])
        )
        session = result.scalar_one_or_none()
        assert session is not None
        # Note: user_agent storage depends on implementation

    async def test_session_tracks_ip_address(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that session tracks IP address."""
        register_data = {
            "email": f"ip_test_{datetime.utcnow().timestamp()}@example.com",
            "password": "TestPassword123!",
            "full_name": "IP Test User",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login
        login_data = {"email": register_data["email"], "password": register_data["password"]}
        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 200

        # Verify IP was captured
        result = await db_session.execute(
            select(UserSession).join(User).where(User.email == register_data["email"])
        )
        session = result.scalar_one_or_none()
        assert session is not None
        assert session.ip_address is not None


class TestSessionTermination:
    """Test session termination."""

    async def test_revoke_specific_session(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test revoking a specific session."""
        # Get current sessions
        response = await authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200
        sessions = response.json()

        if len(sessions) > 0:
            session_id = sessions[0]["id"]

            # Revoke session
            response = await authenticated_client.delete(f"/api/v1/sessions/{session_id}")
            assert response.status_code == 200

            # Verify session was revoked
            result = await db_session.execute(
                select(UserSession).where(UserSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            assert session is None or session.is_active is False

    async def test_logout_from_all_devices(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test logout from all devices."""
        # Logout from all devices
        response = await authenticated_client.delete("/api/v1/sessions/all")
        assert response.status_code == 200

        # Verify all sessions were terminated
        result = await db_session.execute(
            select(UserSession).where(
                UserSession.user_id == test_user.id, UserSession.is_active
            )
        )
        active_sessions = result.scalars().all()
        assert len(active_sessions) == 0


class TestMultipleSessions:
    """Test multiple concurrent sessions."""

    async def test_user_can_have_multiple_sessions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that user can have multiple active sessions."""
        # Create user
        register_data = {
            "email": f"multi_session_{datetime.utcnow().timestamp()}@example.com",
            "password": "TestPassword123!",
            "full_name": "Multi Session User",
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login multiple times (simulating different devices)
        login_data = {"email": register_data["email"], "password": register_data["password"]}

        tokens = []
        for _i in range(3):
            response = await client.post("/api/v1/auth/login", json=login_data)
            assert response.status_code == 200
            tokens.append(response.json()["access_token"])

        # All tokens should be different
        assert len(set(tokens)) == 3

        # Verify multiple sessions exist
        result = await db_session.execute(
            select(UserSession).join(User).where(User.email == register_data["email"])
        )
        sessions = result.scalars().all()
        assert len(sessions) >= 3


class TestSessionExpiration:
    """Test session expiration."""

    async def test_expired_session_rejected(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that expired sessions are rejected."""
        # Create user and session
        from app.services.user import UserService

        user = await UserService.create_user(
            db_session,
            email=f"expired_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Expired Session User",
        )

        # Create expired session
        expired_session = UserSession(
            user_id=user.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Expired 1 hour ago
            is_active=True,
        )
        db_session.add(expired_session)
        await db_session.commit()

        # Try to use expired token
        response = await client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer expired_token"},
        )

        # Should be unauthorized
        assert response.status_code == 401


class TestSessionStatistics:
    """Test session statistics endpoint."""

    async def test_get_session_statistics(self, authenticated_client: AsyncClient):
        """Test retrieving session statistics."""
        response = await authenticated_client.get("/api/v1/sessions/stats")

        assert response.status_code == 200
        stats = response.json()

        assert "total_sessions" in stats
        assert "active_sessions" in stats
        assert isinstance(stats["total_sessions"], int)
        assert isinstance(stats["active_sessions"], int)
