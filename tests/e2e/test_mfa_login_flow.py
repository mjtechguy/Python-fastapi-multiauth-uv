"""E2E tests for MFA (Multi-Factor Authentication) login flow."""

import pytest
import pyotp
from httpx import AsyncClient


class TestMFALoginFlow:
    """Test MFA two-phase authentication flow."""

    @pytest.mark.asyncio
    async def test_login_without_mfa_returns_tokens_directly(
        self, client: AsyncClient, test_user: dict
    ):
        """Test normal login without MFA enabled returns tokens directly."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }

        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        # Should return token object directly
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

        # Should NOT be MFA challenge
        assert "mfa_required" not in data
        assert "mfa_token" not in data

    @pytest.mark.asyncio
    async def test_login_with_mfa_enabled_returns_challenge(
        self, client: AsyncClient, test_user: dict
    ):
        """Test login with MFA enabled returns MFA challenge token."""
        # First, login and setup TOTP
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # Setup TOTP
        setup_response = await client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test Device"},
            headers=headers
        )
        secret = setup_response.json()["secret"]

        # Enable TOTP
        totp = pyotp.TOTP(secret)
        enable_response = await client.post(
            "/api/v1/totp/enable",
            json={"token": totp.now()},
            headers=headers
        )
        assert enable_response.status_code == 200

        # Now login again - should get MFA challenge
        login_response2 = await client.post("/api/v1/auth/login", json=login_data)
        assert login_response2.status_code == 200

        challenge = login_response2.json()
        # Should be MFA challenge, NOT tokens
        assert challenge["mfa_required"] is True
        assert "mfa_token" in challenge
        assert "message" in challenge
        assert "access_token" not in challenge  # No access token yet
        assert "refresh_token" not in challenge  # No refresh token yet

    @pytest.mark.asyncio
    async def test_complete_mfa_login_with_valid_totp(
        self, client: AsyncClient, test_user: dict
    ):
        """Test completing MFA login with valid TOTP code."""
        # Setup: Create user with MFA enabled
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Setup and enable TOTP
        setup_response = await client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test Device"},
            headers=headers
        )
        secret = setup_response.json()["secret"]
        totp = pyotp.TOTP(secret)

        await client.post(
            "/api/v1/totp/enable",
            json={"token": totp.now()},
            headers=headers
        )

        # Phase 1: Login - get MFA challenge
        login_response2 = await client.post("/api/v1/auth/login", json=login_data)
        challenge = login_response2.json()
        mfa_token = challenge["mfa_token"]

        # Phase 2: Complete MFA with valid TOTP
        mfa_data = {
            "mfa_token": mfa_token,
            "totp_code": totp.now()
        }
        mfa_response = await client.post("/api/v1/auth/login/mfa", json=mfa_data)
        assert mfa_response.status_code == 200

        # Should return full tokens now
        tokens = mfa_response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_mfa_login_with_invalid_totp_fails(
        self, client: AsyncClient, test_user: dict
    ):
        """Test MFA login fails with invalid TOTP code."""
        # Setup MFA
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_response = await client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test Device"},
            headers=headers
        )
        secret = setup_response.json()["secret"]
        totp = pyotp.TOTP(secret)

        await client.post(
            "/api/v1/totp/enable",
            json={"token": totp.now()},
            headers=headers
        )

        # Get MFA challenge
        login_response2 = await client.post("/api/v1/auth/login", json=login_data)
        mfa_token = login_response2.json()["mfa_token"]

        # Try with invalid TOTP
        mfa_data = {
            "mfa_token": mfa_token,
            "totp_code": "000000"  # Invalid
        }
        mfa_response = await client.post("/api/v1/auth/login/mfa", json=mfa_data)
        assert mfa_response.status_code == 401
        assert "Invalid MFA token or TOTP code" in mfa_response.json()["detail"]

    @pytest.mark.asyncio
    async def test_mfa_login_with_backup_code_works(
        self, client: AsyncClient, test_user: dict
    ):
        """Test MFA login works with backup code."""
        # Setup MFA
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        setup_response = await client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test Device"},
            headers=headers
        )
        secret = setup_response.json()["secret"]
        backup_codes = setup_response.json()["backup_codes"]
        totp = pyotp.TOTP(secret)

        await client.post(
            "/api/v1/totp/enable",
            json={"token": totp.now()},
            headers=headers
        )

        # Get MFA challenge
        login_response2 = await client.post("/api/v1/auth/login", json=login_data)
        mfa_token = login_response2.json()["mfa_token"]

        # Complete MFA with backup code
        mfa_data = {
            "mfa_token": mfa_token,
            "totp_code": backup_codes[0]  # Use backup code
        }
        mfa_response = await client.post("/api/v1/auth/login/mfa", json=mfa_data)
        assert mfa_response.status_code == 200

        tokens = mfa_response.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens

    @pytest.mark.asyncio
    async def test_mfa_token_expires_after_5_minutes(
        self, client: AsyncClient, test_user: dict
    ):
        """Test MFA challenge token expires (would need time mocking in real test)."""
        # This is a placeholder for a test that would require time mocking
        # The MFA token has a 5-minute expiration set in create_mfa_token()
        # In a real implementation, you'd use freezegun or similar to test expiration
        pass

    @pytest.mark.asyncio
    async def test_mfa_login_with_invalid_mfa_token_fails(
        self, client: AsyncClient, test_user: dict
    ):
        """Test MFA login fails with invalid/tampered MFA token."""
        mfa_data = {
            "mfa_token": "invalid.jwt.token",
            "totp_code": "123456"
        }
        mfa_response = await client.post("/api/v1/auth/login/mfa", json=mfa_data)
        assert mfa_response.status_code == 401
