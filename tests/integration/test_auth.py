"""Integration tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.totp import TOTPSecret
from app.services.totp import TOTPService


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "NewPassword123!",
            "full_name": "New User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["username"] == "newuser"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user):
    """Test registration with duplicate email."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": test_user.email,
            "username": "different",
            "password": "Password123!",
        },
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login(client: AsyncClient, test_user):
    """Test user login."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword123!",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """Test login with wrong password."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, test_user, auth_headers):
    """Test getting current user info."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["username"] == test_user.username


@pytest.mark.asyncio
async def test_refresh_token_flow(client: AsyncClient, test_user):
    """
    Integration test: Verify refresh token flow works end-to-end.

    This tests the fix for session refresh token lookup.
    """
    # Login to get tokens
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword123!",
        },
    )

    assert login_response.status_code == 200
    tokens = login_response.json()
    refresh_token = tokens["refresh_token"]
    old_access_token = tokens["access_token"]

    # Use refresh token to get new access token
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    new_access_token = new_tokens["access_token"]

    # New access token should be different
    assert new_access_token != old_access_token

    # New access token should work
    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {new_access_token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == test_user.email


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test that invalid refresh tokens are rejected."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_token_that_does_not_exist"},
    )

    assert response.status_code in [401, 404]


@pytest.mark.asyncio
async def test_logout_invalidates_session(client: AsyncClient, test_user):
    """Test that logout invalidates the session."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "testpassword123!",
        },
    )

    tokens = login_response.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Logout
    logout_response = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert logout_response.status_code == 200

    # Trying to use refresh token should fail
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code in [401, 404]


@pytest.mark.asyncio
async def test_totp_setup_and_enable_flow(
    client: AsyncClient, test_user, auth_headers, db_session: AsyncSession
):
    """
    Integration test: Complete TOTP setup and enable flow.

    This tests the fix for TOTP backup codes.
    """
    # Setup TOTP
    setup_response = await client.post(
        "/api/v1/totp/setup",
        headers=auth_headers,
        json={"device_name": "Test Device"},
    )

    assert setup_response.status_code == 200
    data = setup_response.json()

    # Should get QR code, secret, and backup codes
    assert "qr_code" in data
    assert "secret" in data
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 10

    backup_codes = data["backup_codes"]

    # Get TOTP secret from database
    result = await db_session.execute(
        select(TOTPSecret).where(TOTPSecret.user_id == test_user.id)
    )
    totp_secret = result.scalar_one()

    # Generate valid TOTP token
    totp_token = TOTPService.generate_totp_token(totp_secret.secret)

    # Enable TOTP
    enable_response = await client.post(
        "/api/v1/totp/enable",
        headers=auth_headers,
        json={"token": totp_token},
    )

    assert enable_response.status_code == 200

    # Verify backup codes work (this tests the fix)
    # Each backup code should validate against stored hashes
    for code in backup_codes:
        is_valid = TOTPService.verify_backup_code(totp_secret, code)
        assert is_valid, f"Backup code '{code}' should be valid"


@pytest.mark.asyncio
async def test_totp_backup_code_login(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Integration test: Login with TOTP backup code.

    Tests that backup codes returned during setup actually work for login.
    """
    # Create user
    from app.services.user import UserService

    user = await UserService.create_user(
        db_session,
        email="totp_backup_test@example.com",
        password="TestPass123!",
        full_name="TOTP Backup Test",
    )
    user.email_verified = True
    await db_session.commit()

    # Login to get token
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TestPass123!"},
    )
    token = login_response.json()["access_token"]

    # Setup TOTP
    setup_response = await client.post(
        "/api/v1/totp/setup",
        headers={"Authorization": f"Bearer {token}"},
        json={"device_name": "Test"},
    )
    backup_codes = setup_response.json()["backup_codes"]
    first_backup_code = backup_codes[0]

    # Get TOTP secret and generate token to enable
    result = await db_session.execute(
        select(TOTPSecret).where(TOTPSecret.user_id == user.id)
    )
    totp_secret = result.scalar_one()
    totp_token = TOTPService.generate_totp_token(totp_secret.secret)

    # Enable TOTP
    await client.post(
        "/api/v1/totp/enable",
        headers={"Authorization": f"Bearer {token}"},
        json={"token": totp_token},
    )

    # Logout
    await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Login with password (will require 2FA)
    await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "TestPass123!"},
    )

    # Use backup code for 2FA
    verify_response = await client.post(
        "/api/v1/auth/verify-2fa",
        json={
            "email": user.email,
            "token": first_backup_code,  # Using backup code
        },
    )

    # Should succeed (this tests the backup codes fix)
    assert verify_response.status_code == 200
    assert "access_token" in verify_response.json()
