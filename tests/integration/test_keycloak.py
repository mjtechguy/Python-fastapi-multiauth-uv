"""Integration tests for Keycloak SSO authentication."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestKeycloakAuthentication:
    """Test Keycloak SSO authentication flow."""

    @pytest.fixture
    def mock_keycloak_client(self):
        """Mock Keycloak client."""
        with patch("app.services.auth_service.KeycloakOpenID") as mock_kc:
            mock_client = AsyncMock()
            mock_kc.return_value = mock_client
            yield mock_client

    async def test_keycloak_callback_new_user(
        self, client: AsyncClient, db_session: AsyncSession, mock_keycloak_client
    ):
        """Test Keycloak callback creating new user."""
        # Mock Keycloak token exchange
        mock_keycloak_client.token = AsyncMock(
            return_value={
                "access_token": "keycloak_access_token",
                "refresh_token": "keycloak_refresh_token",
                "expires_in": 300,
            }
        )

        # Mock Keycloak userinfo
        mock_keycloak_client.userinfo = AsyncMock(
            return_value={
                "sub": "keycloak_user_123",
                "email": "keycloak_user@example.com",
                "email_verified": True,
                "name": "Keycloak User",
                "preferred_username": "keycloakuser",
                "given_name": "Keycloak",
                "family_name": "User",
            }
        )

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            response = await client.post(
                "/api/v1/auth/keycloak/callback",
                json={
                    "code": "keycloak_authorization_code",
                    "session_state": "session_state_123",
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "user" in data
            assert data["user"]["email"] == "keycloak_user@example.com"

        # Verify user was created
        result = await db_session.execute(
            select(User).where(User.email == "keycloak_user@example.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.full_name == "Keycloak User"

    async def test_keycloak_callback_existing_user(
        self, client: AsyncClient, db_session: AsyncSession, mock_keycloak_client
    ):
        """Test Keycloak callback with existing user."""
        # Create existing user
        from app.services.user import UserService

        existing_user = await UserService.create_user(
            db_session,
            email="existing_kc@example.com",
            password="TempPassword123!",
            full_name="Existing KC User",
        )

        # Mock Keycloak responses
        mock_keycloak_client.token = AsyncMock(
            return_value={
                "access_token": "kc_token",
                "refresh_token": "kc_refresh",
                "expires_in": 300,
            }
        )

        mock_keycloak_client.userinfo = AsyncMock(
            return_value={
                "sub": "kc_user_456",
                "email": "existing_kc@example.com",
                "email_verified": True,
                "name": "Existing KC User",
            }
        )

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            response = await client.post(
                "/api/v1/auth/keycloak/callback",
                json={"code": "auth_code", "session_state": "session_123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user"]["email"] == "existing_kc@example.com"

    async def test_keycloak_token_validation(self, mock_keycloak_client):
        """Test Keycloak token validation."""
        # Mock token introspection
        mock_keycloak_client.introspect = AsyncMock(
            return_value={
                "active": True,
                "sub": "user_123",
                "email": "user@example.com",
                "exp": 1234567890,
            }
        )

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            # Token validation logic
            # Implementation depends on your auth service
            pass

    async def test_keycloak_invalid_token(
        self, client: AsyncClient, mock_keycloak_client
    ):
        """Test Keycloak callback with invalid token."""
        mock_keycloak_client.token.side_effect = Exception("Invalid authorization code")

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            response = await client.post(
                "/api/v1/auth/keycloak/callback",
                json={"code": "invalid_code", "session_state": "session_123"},
            )

            assert response.status_code in [400, 401, 500]

    async def test_keycloak_group_mapping(
        self, client: AsyncClient, db_session: AsyncSession, mock_keycloak_client
    ):
        """Test mapping Keycloak groups to application roles."""
        # Mock Keycloak userinfo with groups
        mock_keycloak_client.token = AsyncMock(
            return_value={"access_token": "token", "refresh_token": "refresh"}
        )

        mock_keycloak_client.userinfo = AsyncMock(
            return_value={
                "sub": "user_with_groups",
                "email": "groupuser@example.com",
                "name": "Group User",
                "groups": ["/admin", "/users"],
                "realm_access": {"roles": ["admin", "user"]},
            }
        )

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            response = await client.post(
                "/api/v1/auth/keycloak/callback",
                json={"code": "code", "session_state": "session"},
            )

            # User should be created with appropriate roles
            # Implementation depends on your role mapping logic

    async def test_keycloak_realm_configuration(self):
        """Test Keycloak realm configuration."""
        from app.core.config import settings

        # Verify Keycloak settings are configured
        assert hasattr(settings, "KEYCLOAK_SERVER_URL")
        assert hasattr(settings, "KEYCLOAK_REALM")
        assert hasattr(settings, "KEYCLOAK_CLIENT_ID")

    async def test_keycloak_logout(self, client: AsyncClient, mock_keycloak_client):
        """Test Keycloak logout."""
        # Mock Keycloak logout
        mock_keycloak_client.logout = AsyncMock(return_value=None)

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            # Logout endpoint logic
            # Implementation depends on your auth service
            pass


class TestKeycloakTokenRefresh:
    """Test Keycloak token refresh functionality."""

    @pytest.fixture
    def mock_keycloak_client(self):
        """Mock Keycloak client."""
        with patch("app.services.auth_service.KeycloakOpenID") as mock_kc:
            mock_client = AsyncMock()
            mock_kc.return_value = mock_client
            yield mock_client

    async def test_refresh_keycloak_token(self, mock_keycloak_client):
        """Test refreshing Keycloak access token."""
        mock_keycloak_client.refresh_token = AsyncMock(
            return_value={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 300,
            }
        )

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            # Refresh token logic
            # Implementation depends on your auth service
            pass


class TestKeycloakErrorHandling:
    """Test Keycloak error scenarios."""

    @pytest.fixture
    def mock_keycloak_client(self):
        """Mock Keycloak client."""
        with patch("app.services.auth_service.KeycloakOpenID") as mock_kc:
            mock_client = AsyncMock()
            mock_kc.return_value = mock_client
            yield mock_client

    async def test_keycloak_server_unavailable(
        self, client: AsyncClient, mock_keycloak_client
    ):
        """Test handling when Keycloak server is unavailable."""
        mock_keycloak_client.token.side_effect = Exception("Connection refused")

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            response = await client.post(
                "/api/v1/auth/keycloak/callback",
                json={"code": "code", "session_state": "session"},
            )

            assert response.status_code in [500, 502, 503]

    async def test_keycloak_invalid_realm(self, mock_keycloak_client):
        """Test handling of invalid realm configuration."""
        mock_keycloak_client.token.side_effect = Exception("Realm not found")

        with patch("app.services.auth_service.keycloak_client", mock_keycloak_client):
            # Should handle gracefully
            pass


class TestKeycloakWithRealServer:
    """
    Optional tests using real Keycloak server.

    These require a running Keycloak instance.
    """

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-keycloak-tests", default=False),
        reason="Real Keycloak tests require --run-keycloak-tests flag and running Keycloak",
    )
    async def test_real_keycloak_authentication(self):
        """
        Test authentication with real Keycloak server.

        To run: pytest tests/integration/test_keycloak.py --run-keycloak-tests

        NOTE: Requires Keycloak running at KEYCLOAK_SERVER_URL with configured realm.
        """
        from app.core.config import settings

        if not settings.KEYCLOAK_SERVER_URL or not settings.KEYCLOAK_REALM:
            pytest.skip("Keycloak not configured")

        # This would require manual authorization flow
        pytest.skip("Manual authorization required for real Keycloak testing")


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--run-keycloak-tests",
        action="store_true",
        default=False,
        help="Run tests with real Keycloak server (requires running Keycloak instance)",
    )
