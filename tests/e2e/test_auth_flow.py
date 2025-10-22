"""E2E tests for authentication flows."""

import pytest
from httpx import AsyncClient


class TestAuthenticationFlow:
    """Test complete authentication flows."""

    @pytest.mark.asyncio
    async def test_register_and_login(self, client: AsyncClient):
        """Test user registration and login flow."""
        # Register
        register_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User"
        }

        response = await client.post("/api/v1/auth/register", json=register_data)
        assert response.status_code == 201
        user_data = response.json()
        assert user_data["email"] == register_data["email"]
        assert user_data["full_name"] == register_data["full_name"]
        assert "id" in user_data

        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": register_data["email"],
                "password": register_data["password"]
            }
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token(self, test_user: dict, client: AsyncClient):
        """Test token refresh flow."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": test_user["refresh_token"]}
        )
        assert response.status_code == 200
        new_tokens = response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

    @pytest.mark.asyncio
    async def test_get_current_user(self, authenticated_client: AsyncClient, test_user: dict):
        """Test getting current user info."""
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == test_user["email"]
        assert user_data["full_name"] == test_user["full_name"]

    @pytest.mark.asyncio
    async def test_login_with_wrong_password(self, client: AsyncClient, test_user: dict):
        """Test login with incorrect password."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user["email"],
                "password": "WrongPassword123!"
            }
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client: AsyncClient):
        """Test accessing protected endpoint without authentication."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestEmailVerification:
    """Test email verification flow."""

    @pytest.mark.asyncio
    async def test_email_verification_token_required(self, client: AsyncClient):
        """Test that email verification requires valid token."""
        response = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": "invalid-token"}
        )
        assert response.status_code == 400


class TestPasswordReset:
    """Test password reset flow."""

    @pytest.mark.asyncio
    async def test_request_password_reset(self, client: AsyncClient, test_user: dict):
        """Test requesting password reset."""
        response = await client.post(
            "/api/v1/auth/request-password-reset",
            json={"email": test_user["email"]}
        )
        assert response.status_code == 200
        result = response.json()
        assert "message" in result

    @pytest.mark.asyncio
    async def test_password_reset_invalid_token(self, client: AsyncClient):
        """Test password reset with invalid token."""
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid-token",
                "new_password": "NewPassword123!"
            }
        )
        assert response.status_code == 400
