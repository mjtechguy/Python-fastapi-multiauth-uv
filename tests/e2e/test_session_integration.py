"""E2E tests for session service integration with auth flows."""

import pytest
from httpx import AsyncClient


class TestSessionCreationOnLogin:
    """Test that sessions are created during authentication."""

    @pytest.mark.asyncio
    async def test_local_login_creates_session(
        self, client: AsyncClient, test_user: dict
    ):
        """Test that local login creates a session with device info."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }

        # Login with custom user agent
        headers = {"User-Agent": "Mozilla/5.0 (Test Browser)"}
        response = await client.post(
            "/api/v1/auth/login",
            json=login_data,
            headers=headers
        )
        assert response.status_code == 200

        tokens = response.json()
        auth_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Check that session was created
        session_response = await client.get(
            "/api/v1/sessions",
            headers=auth_headers
        )
        assert session_response.status_code == 200

        sessions = session_response.json()
        assert len(sessions) > 0

        # Verify session has device info
        session = sessions[0]
        assert "user_agent" in session
        assert "ip_address" in session
        assert "device_type" in session

    @pytest.mark.asyncio
    async def test_multiple_logins_create_multiple_sessions(
        self, client: AsyncClient, test_user: dict
    ):
        """Test that multiple logins create multiple sessions."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }

        # First login
        response1 = await client.post("/api/v1/auth/login", json=login_data)
        assert response1.status_code == 200
        token1 = response1.json()["access_token"]

        # Second login (different device)
        headers2 = {"User-Agent": "Mozilla/5.0 (Mobile Device)"}
        response2 = await client.post(
            "/api/v1/auth/login",
            json=login_data,
            headers=headers2
        )
        assert response2.status_code == 200
        token2 = response2.json()["access_token"]

        # Check sessions
        session_response = await client.get(
            "/api/v1/sessions",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert session_response.status_code == 200

        sessions = session_response.json()
        assert len(sessions) >= 2  # Should have at least 2 sessions

    @pytest.mark.asyncio
    async def test_mfa_login_creates_session_after_verification(
        self, client: AsyncClient, test_user: dict
    ):
        """Test that MFA login creates session only after successful verification."""
        # Setup MFA first
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        login_response = await client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Setup and enable TOTP
        import pyotp
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

        # Clear sessions
        session_response = await client.get("/api/v1/sessions", headers=headers)
        for session in session_response.json():
            await client.delete(
                f"/api/v1/sessions/{session['id']}",
                headers=headers
            )

        # Now login with MFA
        login_response2 = await client.post("/api/v1/auth/login", json=login_data)
        mfa_token = login_response2.json()["mfa_token"]

        # Complete MFA
        mfa_data = {
            "mfa_token": mfa_token,
            "totp_code": totp.now()
        }
        mfa_response = await client.post("/api/v1/auth/login/mfa", json=mfa_data)
        assert mfa_response.status_code == 200

        new_token = mfa_response.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}

        # Verify session was created after MFA completion
        session_response = await client.get("/api/v1/sessions", headers=new_headers)
        assert session_response.status_code == 200

        sessions = session_response.json()
        assert len(sessions) >= 1  # Session created after MFA


class TestSessionDeviceTracking:
    """Test that sessions track device information correctly."""

    @pytest.mark.asyncio
    async def test_session_captures_user_agent(
        self, client: AsyncClient, test_user: dict
    ):
        """Test that session captures and parses user agent."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }

        custom_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        headers = {"User-Agent": custom_ua}

        response = await client.post(
            "/api/v1/auth/login",
            json=login_data,
            headers=headers
        )
        assert response.status_code == 200

        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Get sessions
        session_response = await client.get("/api/v1/sessions", headers=auth_headers)
        sessions = session_response.json()

        # Find our session
        our_session = next(
            (s for s in sessions if s.get("user_agent") == custom_ua),
            None
        )
        assert our_session is not None
        assert our_session["device_type"] in ["desktop", "mobile", "tablet"]

    @pytest.mark.asyncio
    async def test_session_captures_ip_address(
        self, client: AsyncClient, test_user: dict
    ):
        """Test that session captures IP address."""
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }

        response = await client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200

        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Get sessions
        session_response = await client.get("/api/v1/sessions", headers=auth_headers)
        sessions = session_response.json()

        assert len(sessions) > 0
        # IP should be captured (testclient or actual IP)
        assert sessions[0].get("ip_address") is not None
