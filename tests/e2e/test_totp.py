"""E2E tests for TOTP (2FA) endpoints."""

import pytest
from httpx import AsyncClient


class TestTOTPSetup:
    """Test TOTP setup flow."""

    @pytest.mark.asyncio
    async def test_setup_totp(self, authenticated_client: AsyncClient):
        """Test setting up TOTP for a user."""
        setup_data = {
            "device_name": "Test Authenticator"
        }

        response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "provisioning_uri" in data
        assert "qr_code" in data
        assert "backup_codes" in data
        assert isinstance(data["backup_codes"], list)
        assert len(data["backup_codes"]) > 0

    @pytest.mark.asyncio
    async def test_setup_totp_already_enabled(self, authenticated_client: AsyncClient):
        """Test setting up TOTP when already enabled."""
        # First setup
        setup_data = {"device_name": "First Device"}
        response1 = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        assert response1.status_code == 200

        # Try to setup again (may succeed or fail depending on implementation)
        response2 = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        # Implementation may allow overwrite or reject
        assert response2.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_setup_totp_unauthorized(self, client: AsyncClient):
        """Test TOTP setup without authentication."""
        setup_data = {"device_name": "Test Device"}
        response = await client.post("/api/v1/totp/setup", json=setup_data)
        assert response.status_code == 401


class TestTOTPEnable:
    """Test TOTP enable flow."""

    @pytest.mark.asyncio
    async def test_enable_totp_with_valid_token(self, authenticated_client: AsyncClient):
        """Test enabling TOTP with a valid token."""
        # Setup TOTP first
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        assert setup_response.status_code == 200
        secret = setup_response.json()["secret"]

        # Generate valid TOTP token
        import pyotp
        totp = pyotp.TOTP(secret)
        token = totp.now()

        # Enable TOTP
        enable_data = {"token": token}
        response = await authenticated_client.post("/api/v1/totp/enable", json=enable_data)
        assert response.status_code == 200
        assert "message" in response.json()

    @pytest.mark.asyncio
    async def test_enable_totp_with_invalid_token(self, authenticated_client: AsyncClient):
        """Test enabling TOTP with invalid token."""
        # Setup TOTP first
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        assert setup_response.status_code == 200

        # Try to enable with invalid token
        enable_data = {"token": "000000"}
        response = await authenticated_client.post("/api/v1/totp/enable", json=enable_data)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_enable_totp_without_setup(self, authenticated_client: AsyncClient):
        """Test enabling TOTP without prior setup."""
        enable_data = {"token": "123456"}
        response = await authenticated_client.post("/api/v1/totp/enable", json=enable_data)
        assert response.status_code == 400


class TestTOTPVerify:
    """Test TOTP verification."""

    @pytest.mark.asyncio
    async def test_verify_valid_totp(self, authenticated_client: AsyncClient):
        """Test verifying a valid TOTP token."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]

        import pyotp
        totp = pyotp.TOTP(secret)
        token = totp.now()

        # Enable TOTP
        enable_data = {"token": token}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Verify TOTP
        verify_data = {"token": totp.now()}
        response = await authenticated_client.post("/api/v1/totp/verify", json=verify_data)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_verify_invalid_totp(self, authenticated_client: AsyncClient):
        """Test verifying an invalid TOTP token."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]

        import pyotp
        totp = pyotp.TOTP(secret)
        token = totp.now()

        enable_data = {"token": token}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Try invalid token
        verify_data = {"token": "000000"}
        response = await authenticated_client.post("/api/v1/totp/verify", json=verify_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_backup_code(self, authenticated_client: AsyncClient):
        """Test verifying with a backup code."""
        # Setup TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]
        backup_codes = setup_response.json()["backup_codes"]

        # Enable TOTP
        import pyotp
        totp = pyotp.TOTP(secret)
        enable_data = {"token": totp.now()}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Verify with backup code
        verify_data = {"token": backup_codes[0]}
        response = await authenticated_client.post("/api/v1/totp/verify", json=verify_data)
        assert response.status_code == 200


class TestTOTPDisable:
    """Test TOTP disable flow."""

    @pytest.mark.asyncio
    async def test_disable_totp_with_correct_password(self, authenticated_client: AsyncClient, test_user: dict):
        """Test disabling TOTP with correct password."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]

        import pyotp
        totp = pyotp.TOTP(secret)
        enable_data = {"token": totp.now()}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Disable TOTP
        disable_data = {"password": test_user["password"]}
        response = await authenticated_client.post("/api/v1/totp/disable", json=disable_data)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_disable_totp_with_wrong_password(self, authenticated_client: AsyncClient):
        """Test disabling TOTP with wrong password."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]

        import pyotp
        totp = pyotp.TOTP(secret)
        enable_data = {"token": totp.now()}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Try to disable with wrong password
        disable_data = {"password": "WrongPassword123!"}
        response = await authenticated_client.post("/api/v1/totp/disable", json=disable_data)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_disable_totp_when_not_enabled(self, authenticated_client: AsyncClient, test_user: dict):
        """Test disabling TOTP when it's not enabled."""
        disable_data = {"password": test_user["password"]}
        response = await authenticated_client.post("/api/v1/totp/disable", json=disable_data)
        assert response.status_code == 400


class TestTOTPStatus:
    """Test TOTP status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_when_disabled(self, authenticated_client: AsyncClient):
        """Test getting TOTP status when not enabled."""
        response = await authenticated_client.get("/api/v1/totp/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is False
        assert data["is_verified"] is False
        assert data["backup_codes_remaining"] == 0

    @pytest.mark.asyncio
    async def test_get_status_when_enabled(self, authenticated_client: AsyncClient):
        """Test getting TOTP status when enabled."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]

        import pyotp
        totp = pyotp.TOTP(secret)
        enable_data = {"token": totp.now()}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Get status
        response = await authenticated_client.get("/api/v1/totp/status")
        assert response.status_code == 200
        data = response.json()
        assert data["is_enabled"] is True
        assert "device_name" in data
        assert "backup_codes_remaining" in data

    @pytest.mark.asyncio
    async def test_get_status_unauthorized(self, client: AsyncClient):
        """Test getting TOTP status without authentication."""
        response = await client.get("/api/v1/totp/status")
        assert response.status_code == 401


class TestBackupCodes:
    """Test backup code regeneration."""

    @pytest.mark.asyncio
    async def test_regenerate_backup_codes(self, authenticated_client: AsyncClient, test_user: dict):
        """Test regenerating backup codes."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]
        original_codes = setup_response.json()["backup_codes"]

        import pyotp
        totp = pyotp.TOTP(secret)
        enable_data = {"token": totp.now()}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Regenerate backup codes
        regen_data = {"password": test_user["password"]}
        response = await authenticated_client.post("/api/v1/totp/backup-codes", json=regen_data)
        assert response.status_code == 200
        data = response.json()
        assert "backup_codes" in data
        assert isinstance(data["backup_codes"], list)
        # New codes should be different
        assert data["backup_codes"] != original_codes

    @pytest.mark.asyncio
    async def test_regenerate_backup_codes_wrong_password(self, authenticated_client: AsyncClient):
        """Test regenerating backup codes with wrong password."""
        # Setup and enable TOTP
        setup_data = {"device_name": "Test Device"}
        setup_response = await authenticated_client.post("/api/v1/totp/setup", json=setup_data)
        secret = setup_response.json()["secret"]

        import pyotp
        totp = pyotp.TOTP(secret)
        enable_data = {"token": totp.now()}
        await authenticated_client.post("/api/v1/totp/enable", json=enable_data)

        # Try to regenerate with wrong password
        regen_data = {"password": "WrongPassword123!"}
        response = await authenticated_client.post("/api/v1/totp/backup-codes", json=regen_data)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_regenerate_backup_codes_without_totp(self, authenticated_client: AsyncClient, test_user: dict):
        """Test regenerating backup codes when TOTP not enabled."""
        regen_data = {"password": test_user["password"]}
        response = await authenticated_client.post("/api/v1/totp/backup-codes", json=regen_data)
        assert response.status_code == 400
