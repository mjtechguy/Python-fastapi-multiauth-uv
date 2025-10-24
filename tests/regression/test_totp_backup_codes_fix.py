"""Regression test for TOTP backup codes validation fix.

Issue: After TOTPService.setup_totp hashed the original backup codes,
the endpoint generated a fresh set of codes to return, meaning users
received codes that would NEVER validate against the stored hashes.

Fix: Modified setup_totp to return the plaintext backup codes before
hashing, and endpoint uses those same codes.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.totp import TOTPSecret
from app.models.user import User
from app.services.totp import TOTPService


@pytest.mark.asyncio
class TestTOTPBackupCodesFix:
    """Test that TOTP backup codes work correctly after the fix."""

    async def test_backup_codes_validate_after_setup(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that backup codes returned during setup actually validate.

        This is the main regression test for the fix.
        """
        # Setup TOTP
        response = await authenticated_client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test Device"},
        )

        assert response.status_code == 200
        data = response.json()

        # Extract backup codes from setup response
        backup_codes = data["backup_codes"]
        assert len(backup_codes) == 10, "Should receive 10 backup codes"

        # Get the TOTP secret from database
        result = await db_session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == test_user.id)
        )
        totp_secret = result.scalar_one()

        assert totp_secret is not None
        assert len(totp_secret.backup_codes) == 10, "Should have 10 hashed codes stored"

        # Verify that EACH backup code validates
        for i, code in enumerate(backup_codes):
            # Use the service method to validate
            is_valid = TOTPService.verify_backup_code(totp_secret, code)
            assert is_valid, f"Backup code {i} ('{code}') should validate but doesn't"

    async def test_backup_codes_can_be_used_for_login(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test end-to-end: Setup TOTP, enable it, then use backup code to login.
        """
        # Create and login a user
        from app.services.user import UserService

        user = await UserService.create_user(
            db_session,
            email=f"totp_test_{pytest.approx}@test.com",
            password="TestPass123!",
            full_name="TOTP Test User",
        )
        user.email_verified = True
        await db_session.commit()

        # Login to get token
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        # Setup TOTP
        setup_response = await client.post(
            "/api/v1/totp/setup",
            headers={"Authorization": f"Bearer {token}"},
            json={"device_name": "Test"},
        )
        assert setup_response.status_code == 200
        backup_codes = setup_response.json()["backup_codes"]
        first_backup_code = backup_codes[0]

        # Generate valid TOTP token to enable 2FA
        result = await db_session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == user.id)
        )
        totp_secret = result.scalar_one()
        totp_token = TOTPService.generate_totp_token(totp_secret.secret)

        # Enable TOTP
        enable_response = await client.post(
            "/api/v1/totp/enable",
            headers={"Authorization": f"Bearer {token}"},
            json={"token": totp_token},
        )
        assert enable_response.status_code == 200

        # Logout
        await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Try to login with backup code instead of TOTP token
        # First, login with password to get to 2FA challenge
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )

        # Now provide backup code for 2FA
        verify_response = await client.post(
            "/api/v1/auth/verify-2fa",
            json={
                "email": user.email,
                "token": first_backup_code,  # Using backup code
            },
        )

        assert verify_response.status_code == 200, \
            f"Backup code should work for 2FA: {verify_response.text}"
        assert "access_token" in verify_response.json()

    async def test_backup_code_used_once_becomes_invalid(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that backup codes can only be used once.
        """
        # Setup TOTP
        response = await authenticated_client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test"},
        )
        backup_codes = response.json()["backup_codes"]
        test_code = backup_codes[0]

        # Get TOTP secret
        result = await db_session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == test_user.id)
        )
        totp_secret = result.scalar_one()

        # First use - should work
        is_valid_first = TOTPService.verify_backup_code(totp_secret, test_code)
        assert is_valid_first, "First use of backup code should be valid"

        # After first use, the code should be removed from the list
        # Verify it
        result = await db_session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == test_user.id)
        )
        totp_secret_after = result.scalar_one()

        # Second use - should fail
        is_valid_second = TOTPService.verify_backup_code(totp_secret_after, test_code)
        assert not is_valid_second, "Backup code should not work after being used once"

    async def test_setup_totp_returns_same_codes_that_are_stored(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Regression test: Verify that setup_totp returns the SAME codes
        that are hashed and stored.

        Before the fix, it hashed codes, then generated NEW codes to return.
        """
        # Call setup_totp directly
        totp_secret, _uri, _qr_code, backup_codes = await TOTPService.setup_totp(
            db_session, test_user, "Test Device"
        )

        await db_session.commit()

        # The backup_codes returned should match the hashed codes stored
        assert len(backup_codes) == 10
        assert len(totp_secret.backup_codes) == 10

        # Verify each plaintext code validates against the stored hashes
        from app.core.security import verify_password

        for plaintext_code in backup_codes:
            # At least one hash should match this code
            matches = [
                verify_password(plaintext_code, hashed)
                for hashed in totp_secret.backup_codes
            ]
            assert any(matches), \
                f"Code '{plaintext_code}' should match one of the stored hashes"

    async def test_multiple_backup_codes_all_valid(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that all 10 backup codes work, not just the first one.
        """
        # Setup TOTP
        response = await authenticated_client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Test"},
        )
        backup_codes = response.json()["backup_codes"]

        # Get TOTP secret
        result = await db_session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == test_user.id)
        )
        totp_secret = result.scalar_one()

        # Test all 10 codes
        valid_count = 0
        for code in backup_codes:
            if TOTPService.verify_backup_code(totp_secret, code):
                valid_count += 1

        assert valid_count == 10, \
            f"All 10 backup codes should be valid, but only {valid_count} were"

    async def test_backup_codes_regenerated_on_new_setup(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that calling setup again generates NEW backup codes.
        """
        # First setup
        response1 = await authenticated_client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Device 1"},
        )
        backup_codes_1 = response1.json()["backup_codes"]

        # Second setup (re-setup)
        response2 = await authenticated_client.post(
            "/api/v1/totp/setup",
            json={"device_name": "Device 2"},
        )
        backup_codes_2 = response2.json()["backup_codes"]

        # Codes should be different
        assert set(backup_codes_1) != set(backup_codes_2), \
            "New setup should generate different backup codes"

        # Old codes should NOT work with new setup
        result = await db_session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == test_user.id)
        )
        totp_secret = result.scalar_one()

        for old_code in backup_codes_1:
            is_valid = TOTPService.verify_backup_code(totp_secret, old_code)
            assert not is_valid, \
                f"Old backup code '{old_code}' should not work after re-setup"

        # New codes SHOULD work
        for new_code in backup_codes_2:
            is_valid = TOTPService.verify_backup_code(totp_secret, new_code)
            assert is_valid, \
                f"New backup code '{new_code}' should work"
