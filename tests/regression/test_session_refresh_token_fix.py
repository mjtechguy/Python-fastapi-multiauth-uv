"""Regression test for session refresh token lookup fix.

Issue: Refresh-token lookups re-hashed the presented token and used
'not UserSession.revoked', causing:
1. Token comparison to always fail (hashing isn't deterministic)
2. SQLAlchemy crash on 'not' operator

Fix: Changed to verify_password() for token comparison and .is_(False)
for SQLAlchemy boolean checks.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.session import UserSession
from app.models.user import User
from app.services.session import SessionService


@pytest.mark.asyncio
class TestSessionRefreshTokenFix:
    """Test that session refresh tokens work correctly after the fix."""

    async def test_refresh_token_lookup_succeeds(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test that refresh tokens can be looked up and validated.

        This is the main regression test - it would have failed before the fix.
        """
        # Create and login a user
        from app.services.user import UserService

        user = await UserService.create_user(
            db_session,
            email=f"refresh_test_{pytest.approx}@test.com",
            password="TestPass123!",
            full_name="Refresh Test",
        )
        user.email_verified = True
        await db_session.commit()

        # Login to create a session
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )

        assert login_response.status_code == 200
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # Use the refresh token to get a new access token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert refresh_response.status_code == 200, \
            f"Refresh token should work: {refresh_response.text}"

        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

    async def test_session_service_get_by_token_uses_verify_password(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Regression test: Verify that get_session_by_token uses verify_password
        instead of re-hashing the token.
        """
        # Create a session with known refresh token
        from app.core.security import get_password_hash

        plaintext_token = "test_refresh_token_123"
        hashed_token = get_password_hash(plaintext_token)

        session = UserSession(
            user_id=test_user.id,
            token_hash=hashed_token,
            device_info="Test Device",
            ip_address="127.0.0.1",
            user_agent="Test Agent",
        )
        db_session.add(session)
        await db_session.commit()

        # Try to retrieve session using the plaintext token
        found_session = await SessionService.get_session_by_token(
            db_session, plaintext_token
        )

        assert found_session is not None, \
            "Session should be found using plaintext token"
        assert found_session.id == session.id
        assert verify_password(plaintext_token, found_session.token_hash)

    async def test_boolean_syntax_for_revoked_sessions(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Regression test: Verify that .is_(False) syntax works for
        revoked and is_active checks.

        The old 'not UserSession.revoked' would cause SQLAlchemy error.
        """
        from app.core.security import get_password_hash

        # Create active, non-revoked session
        active_session = UserSession(
            user_id=test_user.id,
            token_hash=get_password_hash("active_token"),
            device_info="Active",
            ip_address="127.0.0.1",
            user_agent="Test",
            is_active=True,
            revoked=False,
        )

        # Create revoked session
        revoked_session = UserSession(
            user_id=test_user.id,
            token_hash=get_password_hash("revoked_token"),
            device_info="Revoked",
            ip_address="127.0.0.1",
            user_agent="Test",
            is_active=False,
            revoked=True,
        )

        db_session.add(active_session)
        db_session.add(revoked_session)
        await db_session.commit()

        # Query using CORRECT SQLAlchemy syntax
        result = await db_session.execute(
            select(UserSession).where(
                UserSession.user_id == test_user.id,
                UserSession.is_active.is_(True),  # CORRECT
                UserSession.revoked.is_(False),   # CORRECT
            )
        )
        active_sessions = result.scalars().all()

        assert len(active_sessions) == 1
        assert active_sessions[0].id == active_session.id

    async def test_multiple_sessions_token_lookup_finds_correct_one(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that when multiple sessions exist, the correct one is found
        by its refresh token.
        """
        from app.core.security import get_password_hash

        # Create 3 sessions with different tokens
        sessions_data = [
            ("token_session_1", "Device 1"),
            ("token_session_2", "Device 2"),
            ("token_session_3", "Device 3"),
        ]

        created_sessions = []
        for token, device in sessions_data:
            session = UserSession(
                user_id=test_user.id,
                token_hash=get_password_hash(token),
                device_info=device,
                ip_address="127.0.0.1",
                user_agent="Test",
            )
            db_session.add(session)
            created_sessions.append((token, session))

        await db_session.commit()

        # Look up each session by its token
        for plaintext_token, original_session in created_sessions:
            found_session = await SessionService.get_session_by_token(
                db_session, plaintext_token
            )

            assert found_session is not None
            assert found_session.id == original_session.id
            assert found_session.device_info == original_session.device_info

    async def test_invalid_token_returns_none(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that an invalid/non-existent refresh token returns None.
        """
        from app.core.security import get_password_hash

        # Create a valid session
        session = UserSession(
            user_id=test_user.id,
            token_hash=get_password_hash("valid_token"),
            device_info="Test",
            ip_address="127.0.0.1",
            user_agent="Test",
        )
        db_session.add(session)
        await db_session.commit()

        # Try to look up with wrong token
        found = await SessionService.get_session_by_token(
            db_session, "wrong_token_that_does_not_exist"
        )

        assert found is None

    async def test_revoked_session_not_returned(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that revoked sessions are not returned by get_session_by_token.
        """
        from app.core.security import get_password_hash

        plaintext_token = "revoked_session_token"

        # Create a revoked session
        session = UserSession(
            user_id=test_user.id,
            token_hash=get_password_hash(plaintext_token),
            device_info="Revoked Session",
            ip_address="127.0.0.1",
            user_agent="Test",
            revoked=True,
        )
        db_session.add(session)
        await db_session.commit()

        # Try to look it up - should return None because it's revoked
        found = await SessionService.get_session_by_token(
            db_session, plaintext_token
        )

        assert found is None, "Revoked sessions should not be returned"

    async def test_expired_session_not_returned(
        self,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that expired sessions are not returned.
        """
        from datetime import UTC, datetime, timedelta

        from app.core.security import get_password_hash

        plaintext_token = "expired_session_token"

        # Create an expired session (expires_at in the past)
        session = UserSession(
            user_id=test_user.id,
            token_hash=get_password_hash(plaintext_token),
            device_info="Expired Session",
            ip_address="127.0.0.1",
            user_agent="Test",
            expires_at=datetime.now(UTC) - timedelta(days=1),  # Expired yesterday
        )
        db_session.add(session)
        await db_session.commit()

        # Try to look it up - should return None because it's expired
        found = await SessionService.get_session_by_token(
            db_session, plaintext_token
        )

        assert found is None, "Expired sessions should not be returned"

    async def test_refresh_updates_last_activity(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test that using a refresh token updates the session's last_activity.
        """

        from app.services.user import UserService

        # Create user and login
        user = await UserService.create_user(
            db_session,
            email=f"activity_test_{pytest.approx}@test.com",
            password="TestPass123!",
            full_name="Activity Test",
        )
        user.email_verified = True
        await db_session.commit()

        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Get initial last_activity
        result = await db_session.execute(
            select(UserSession).where(UserSession.user_id == user.id)
        )
        session_before = result.scalar_one()
        last_activity_before = session_before.last_activity

        # Wait a moment
        await db_session.execute("SELECT pg_sleep(0.1)")

        # Use refresh token
        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        # Check last_activity was updated
        await db_session.refresh(session_before)
        last_activity_after = session_before.last_activity

        assert last_activity_after > last_activity_before, \
            "last_activity should be updated when refresh token is used"

    async def test_end_to_end_token_refresh_flow(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test complete flow: login -> refresh -> use new token.
        """
        from app.services.user import UserService

        user = await UserService.create_user(
            db_session,
            email=f"e2e_refresh_{pytest.approx}@test.com",
            password="TestPass123!",
            full_name="E2E Test",
        )
        user.email_verified = True
        await db_session.commit()

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "TestPass123!"},
        )
        assert login_response.status_code == 200
        old_access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        # 2. Use refresh token to get new access token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        new_access_token = refresh_response.json()["access_token"]

        # Tokens should be different
        assert new_access_token != old_access_token

        # 3. Use new access token to access protected endpoint
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {new_access_token}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["email"] == user.email
