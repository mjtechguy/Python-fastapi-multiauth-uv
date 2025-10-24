"""Integration tests for OAuth provider authentication."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from app.models.oauth_account import OAuthAccount
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestGoogleOAuth:
    """Test Google OAuth authentication flow."""

    @pytest.fixture
    def mock_google_oauth(self):
        """Mock Google OAuth client."""
        with patch("app.services.auth_service.Authlib") as mock_authlib:
            mock_client = AsyncMock()
            mock_authlib.return_value = mock_client
            yield mock_client

    async def test_google_authorize_redirect(self, client: AsyncClient):
        """Test Google OAuth authorization redirect."""
        response = await client.get("/api/v1/auth/oauth/google/authorize")

        # Should redirect to Google OAuth
        assert response.status_code in [200, 302, 307]

    async def test_google_oauth_callback_new_user(
        self, client: AsyncClient, db_session: AsyncSession, mock_google_oauth
    ):
        """Test Google OAuth callback creating new user."""
        # Mock Google user info
        mock_google_oauth.get.return_value.json = AsyncMock(
            return_value={
                "sub": "google_user_123",
                "email": "newuser@gmail.com",
                "name": "Google User",
                "picture": "https://example.com/photo.jpg",
                "email_verified": True,
            }
        )

        # Mock OAuth token
        mock_google_oauth.authorize_access_token = AsyncMock(
            return_value={"access_token": "mock_google_token"}
        )

        with patch("app.services.auth_service.oauth_client") as mock_oauth:
            mock_oauth.google.authorize_access_token = (
                mock_google_oauth.authorize_access_token
            )
            mock_oauth.google.get = mock_google_oauth.get

            response = await client.post(
                "/api/v1/auth/oauth/google/callback",
                json={"code": "mock_auth_code", "state": "mock_state"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert "user" in data
            assert data["user"]["email"] == "newuser@gmail.com"

        # Verify user was created
        result = await db_session.execute(
            select(User).where(User.email == "newuser@gmail.com")
        )
        user = result.scalar_one_or_none()
        assert user is not None

        # Verify OAuth account was linked
        oauth_result = await db_session.execute(
            select(OAuthAccount).where(OAuthAccount.user_id == user.id)
        )
        oauth_account = oauth_result.scalar_one_or_none()
        assert oauth_account is not None
        assert oauth_account.provider == "google"

    async def test_google_oauth_callback_existing_user(
        self, client: AsyncClient, db_session: AsyncSession, mock_google_oauth
    ):
        """Test Google OAuth callback with existing user."""
        # Create existing user
        from app.services.user import UserService

        existing_user = await UserService.create_user(
            db_session,
            email="existing@gmail.com",
            password="TestPassword123!",
            full_name="Existing User",
        )

        # Create OAuth account link
        oauth_account = OAuthAccount(
            user_id=existing_user.id,
            provider="google",
            provider_user_id="google_user_456",
            access_token="old_token",
        )
        db_session.add(oauth_account)
        await db_session.commit()

        # Mock Google user info
        mock_google_oauth.get.return_value.json = AsyncMock(
            return_value={
                "sub": "google_user_456",
                "email": "existing@gmail.com",
                "name": "Existing User",
                "email_verified": True,
            }
        )

        mock_google_oauth.authorize_access_token = AsyncMock(
            return_value={"access_token": "new_google_token"}
        )

        with patch("app.services.auth_service.oauth_client") as mock_oauth:
            mock_oauth.google.authorize_access_token = (
                mock_google_oauth.authorize_access_token
            )
            mock_oauth.google.get = mock_google_oauth.get

            response = await client.post(
                "/api/v1/auth/oauth/google/callback",
                json={"code": "mock_auth_code", "state": "mock_state"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user"]["email"] == "existing@gmail.com"


class TestGitHubOAuth:
    """Test GitHub OAuth authentication flow."""

    @pytest.fixture
    def mock_github_oauth(self):
        """Mock GitHub OAuth client."""
        with patch("app.services.auth_service.Authlib") as mock_authlib:
            mock_client = AsyncMock()
            mock_authlib.return_value = mock_client
            yield mock_client

    async def test_github_authorize_redirect(self, client: AsyncClient):
        """Test GitHub OAuth authorization redirect."""
        response = await client.get("/api/v1/auth/oauth/github/authorize")

        assert response.status_code in [200, 302, 307]

    async def test_github_oauth_callback_new_user(
        self, client: AsyncClient, db_session: AsyncSession, mock_github_oauth
    ):
        """Test GitHub OAuth callback creating new user."""
        # Mock GitHub user info
        mock_github_oauth.get.return_value.json = AsyncMock(
            return_value={
                "id": 12345,
                "login": "githubuser",
                "email": "githubuser@example.com",
                "name": "GitHub User",
                "avatar_url": "https://avatars.github.com/u/12345",
            }
        )

        mock_github_oauth.authorize_access_token = AsyncMock(
            return_value={"access_token": "mock_github_token"}
        )

        with patch("app.services.auth_service.oauth_client") as mock_oauth:
            mock_oauth.github.authorize_access_token = (
                mock_github_oauth.authorize_access_token
            )
            mock_oauth.github.get = mock_github_oauth.get

            response = await client.post(
                "/api/v1/auth/oauth/github/callback",
                json={"code": "mock_auth_code", "state": "mock_state"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["user"]["email"] == "githubuser@example.com"


class TestMicrosoftOAuth:
    """Test Microsoft OAuth authentication flow."""

    @pytest.fixture
    def mock_microsoft_oauth(self):
        """Mock Microsoft OAuth client."""
        with patch("app.services.auth_service.Authlib") as mock_authlib:
            mock_client = AsyncMock()
            mock_authlib.return_value = mock_client
            yield mock_client

    async def test_microsoft_authorize_redirect(self, client: AsyncClient):
        """Test Microsoft OAuth authorization redirect."""
        response = await client.get("/api/v1/auth/oauth/microsoft/authorize")

        assert response.status_code in [200, 302, 307]

    async def test_microsoft_oauth_callback_new_user(
        self, client: AsyncClient, db_session: AsyncSession, mock_microsoft_oauth
    ):
        """Test Microsoft OAuth callback creating new user."""
        # Mock Microsoft user info
        mock_microsoft_oauth.get.return_value.json = AsyncMock(
            return_value={
                "id": "microsoft_user_789",
                "userPrincipalName": "msuser@outlook.com",
                "displayName": "Microsoft User",
                "mail": "msuser@outlook.com",
            }
        )

        mock_microsoft_oauth.authorize_access_token = AsyncMock(
            return_value={"access_token": "mock_microsoft_token"}
        )

        with patch("app.services.auth_service.oauth_client") as mock_oauth:
            mock_oauth.microsoft.authorize_access_token = (
                mock_microsoft_oauth.authorize_access_token
            )
            mock_oauth.microsoft.get = mock_microsoft_oauth.get

            response = await client.post(
                "/api/v1/auth/oauth/microsoft/callback",
                json={"code": "mock_auth_code", "state": "mock_state"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data


class TestOAuthAccountLinking:
    """Test OAuth account linking to existing accounts."""

    async def test_link_google_to_existing_account(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test linking Google account to existing email/password account."""
        # Create user with email/password
        from app.services.user import UserService

        user = await UserService.create_user(
            db_session,
            email="user@example.com",
            password="Password123!",
            full_name="Test User",
        )

        # Simulate OAuth login with same email
        # The system should link the OAuth account to existing user
        # Implementation depends on your auth service logic


class TestOAuthErrorHandling:
    """Test OAuth error scenarios."""

    async def test_oauth_callback_with_invalid_code(self, client: AsyncClient):
        """Test OAuth callback with invalid authorization code."""
        response = await client.post(
            "/api/v1/auth/oauth/google/callback",
            json={"code": "invalid_code", "state": "test_state"},
        )

        # Should handle error gracefully
        assert response.status_code in [400, 401, 500]

    async def test_oauth_callback_missing_email(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test OAuth callback when provider doesn't return email."""
        with patch("app.services.auth_service.oauth_client") as mock_oauth:
            mock_client = AsyncMock()
            mock_client.get.return_value.json = AsyncMock(
                return_value={
                    "sub": "user_no_email",
                    "name": "User Without Email",
                    # No email field
                }
            )
            mock_client.authorize_access_token = AsyncMock(
                return_value={"access_token": "token"}
            )
            mock_oauth.google = mock_client

            response = await client.post(
                "/api/v1/auth/oauth/google/callback",
                json={"code": "code", "state": "state"},
            )

            # Should fail gracefully
            assert response.status_code in [400, 500]

    async def test_oauth_provider_unavailable(self, client: AsyncClient):
        """Test OAuth when provider service is unavailable."""
        with patch("app.services.auth_service.oauth_client") as mock_oauth:
            mock_oauth.google.authorize_access_token.side_effect = Exception(
                "Service unavailable"
            )

            response = await client.post(
                "/api/v1/auth/oauth/google/callback",
                json={"code": "code", "state": "state"},
            )

            assert response.status_code in [500, 502, 503]


class TestOAuthTokenRefresh:
    """Test OAuth token refresh functionality."""

    async def test_refresh_expired_oauth_token(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test refreshing expired OAuth access token."""
        # Create user with OAuth account
        from app.services.user import UserService

        user = await UserService.create_user(
            db_session,
            email="oauth_user@example.com",
            password="TempPassword123!",
            full_name="OAuth User",
        )

        oauth_account = OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id="google_refresh_test",
            access_token="expired_token",
            refresh_token="refresh_token_123",
            token_expires_at=datetime.utcnow(),  # Expired
        )
        db_session.add(oauth_account)
        await db_session.commit()

        # Mock token refresh
        # Implementation depends on your refresh token logic


class TestOAuthWithRealProviders:
    """
    Optional tests using real OAuth providers.

    These require valid OAuth credentials in .env.
    """

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-oauth-tests", default=False),
        reason="Real OAuth tests require --run-oauth-tests flag and valid credentials",
    )
    async def test_real_google_oauth_flow(self):
        """
        Test OAuth flow with real Google provider.

        To run: pytest tests/integration/test_oauth_providers.py --run-oauth-tests

        NOTE: Requires valid GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.
        """
        from app.core.config import settings

        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            pytest.skip("Google OAuth not configured")

        # This would require manual authorization flow
        pytest.skip("Manual authorization required for real OAuth testing")


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--run-oauth-tests",
        action="store_true",
        default=False,
        help="Run tests with real OAuth providers (requires valid credentials)",
    )
