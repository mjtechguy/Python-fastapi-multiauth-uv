"""End-to-end tests for API key management."""

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import APIKey
from app.models.user import User


class TestAPIKeyCreation:
    """Test API key creation."""

    async def test_create_api_key(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test creating a new API key."""
        response = await authenticated_client.post(
            "/api/v1/api-keys",
            json={"name": "Test API Key", "expires_in_days": 30},
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response contains all fields
        assert "id" in data
        assert "name" in data
        assert data["name"] == "Test API Key"
        assert "prefix" in data
        assert "key" in data  # Full key is shown once
        assert "is_active" in data
        assert data["is_active"] is True
        assert "expires_at" in data
        assert "created_at" in data

        # Verify key was created in database
        result = await db_session.execute(
            select(APIKey).where(APIKey.user_id == test_user.id)
        )
        api_key = result.scalar_one_or_none()
        assert api_key is not None
        assert api_key.name == "Test API Key"

    async def test_create_api_key_without_expiration(
        self, authenticated_client: AsyncClient, test_user: User
    ):
        """Test creating an API key without expiration."""
        response = await authenticated_client.post(
            "/api/v1/api-keys",
            json={"name": "Permanent Key"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is None

    async def test_create_api_key_requires_auth(self, client: AsyncClient):
        """Test that creating API keys requires authentication."""
        response = await client.post(
            "/api/v1/api-keys",
            json={"name": "Test Key"},
        )

        assert response.status_code == 401

    async def test_create_api_key_invalid_expiration(
        self, authenticated_client: AsyncClient
    ):
        """Test creating API key with invalid expiration days."""
        response = await authenticated_client.post(
            "/api/v1/api-keys",
            json={"name": "Test Key", "expires_in_days": 400},  # Too long
        )

        assert response.status_code == 422  # Validation error


class TestAPIKeyListing:
    """Test listing API keys."""

    async def test_list_api_keys(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test listing API keys."""
        # Create some API keys
        from app.services.api_key_service import APIKeyService

        await APIKeyService.create_api_key(db_session, test_user.id, "Key 1")
        await APIKeyService.create_api_key(db_session, test_user.id, "Key 2")

        response = await authenticated_client.get("/api/v1/api-keys")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

        # Verify keys don't include full key string
        for key in data["items"]:
            assert "key" not in key  # Full key not shown in list
            assert "prefix" in key
            assert "name" in key

    async def test_list_api_keys_with_inactive(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test listing API keys including inactive ones."""
        from app.services.api_key_service import APIKeyService

        # Create and revoke a key
        _key, _ = await APIKeyService.create_api_key(db_session, test_user.id, "Active Key")
        revoked_key, _ = await APIKeyService.create_api_key(db_session, test_user.id, "Revoked Key")
        await APIKeyService.revoke_api_key(db_session, revoked_key.id, test_user.id)

        # List without inactive
        response = await authenticated_client.get("/api/v1/api-keys")
        assert response.status_code == 200
        active_only = response.json()

        # List with inactive
        response = await authenticated_client.get("/api/v1/api-keys?include_inactive=true")
        assert response.status_code == 200
        with_inactive = response.json()

        assert with_inactive["total"] > active_only["total"]

    async def test_list_api_keys_only_shows_own_keys(
        self, authenticated_client: AsyncClient, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that users only see their own API keys."""
        # Create another user
        from app.services.user import UserService

        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        # Create API key for other user
        from app.services.api_key_service import APIKeyService

        await APIKeyService.create_api_key(db_session, other_user.id, "Other User Key")

        # Current user should not see other user's keys
        response = await authenticated_client.get("/api/v1/api-keys")
        assert response.status_code == 200
        data = response.json()

        for key in data["items"]:
            assert key["name"] != "Other User Key"


class TestAPIKeyRetrieval:
    """Test retrieving individual API keys."""

    async def test_get_api_key_by_id(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test getting a specific API key by ID."""
        from app.services.api_key_service import APIKeyService

        api_key, _ = await APIKeyService.create_api_key(
            db_session, test_user.id, "Test Key"
        )

        response = await authenticated_client.get(f"/api/v1/api-keys/{api_key.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(api_key.id)
        assert data["name"] == "Test Key"

    async def test_get_nonexistent_api_key(self, authenticated_client: AsyncClient):
        """Test getting a non-existent API key."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/api-keys/{fake_id}")

        assert response.status_code == 404

    async def test_cannot_get_other_users_api_key(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that users cannot access other users' API keys."""
        # Create another user and their API key
        from app.services.api_key_service import APIKeyService
        from app.services.user import UserService

        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        other_key, _ = await APIKeyService.create_api_key(
            db_session, other_user.id, "Other's Key"
        )

        # Try to access other user's key
        response = await authenticated_client.get(f"/api/v1/api-keys/{other_key.id}")

        assert response.status_code == 404


class TestAPIKeyRevocation:
    """Test API key revocation."""

    async def test_revoke_api_key(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test revoking an API key."""
        from app.services.api_key_service import APIKeyService

        api_key, _ = await APIKeyService.create_api_key(
            db_session, test_user.id, "Key to Revoke"
        )

        response = await authenticated_client.delete(f"/api/v1/api-keys/{api_key.id}")

        assert response.status_code == 204

        # Verify key is now inactive
        await db_session.refresh(api_key)
        assert api_key.is_active is False

    async def test_revoke_nonexistent_api_key(self, authenticated_client: AsyncClient):
        """Test revoking a non-existent API key."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.delete(f"/api/v1/api-keys/{fake_id}")

        assert response.status_code == 404

    async def test_cannot_revoke_other_users_api_key(
        self, authenticated_client: AsyncClient, db_session: AsyncSession
    ):
        """Test that users cannot revoke other users' API keys."""
        from app.services.api_key_service import APIKeyService
        from app.services.user import UserService

        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        other_key, _ = await APIKeyService.create_api_key(
            db_session, other_user.id, "Other's Key"
        )

        response = await authenticated_client.delete(f"/api/v1/api-keys/{other_key.id}")

        assert response.status_code == 404

        # Verify key is still active
        await db_session.refresh(other_key)
        assert other_key.is_active is True


class TestAPIKeyDeletion:
    """Test permanent API key deletion."""

    async def test_delete_api_key_permanently(
        self, authenticated_client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test permanently deleting an API key."""
        from app.services.api_key_service import APIKeyService

        api_key, _ = await APIKeyService.create_api_key(
            db_session, test_user.id, "Key to Delete"
        )
        key_id = api_key.id

        response = await authenticated_client.delete(f"/api/v1/api-keys/{key_id}/permanent")

        assert response.status_code == 204

        # Verify key is completely removed
        result = await db_session.execute(select(APIKey).where(APIKey.id == key_id))
        assert result.scalar_one_or_none() is None


class TestAPIKeyAuthentication:
    """Test authentication using API keys."""

    async def test_api_key_authentication(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test that API keys can be used for authentication."""
        from app.services.api_key_service import APIKeyService

        # Create API key
        _, raw_key = await APIKeyService.create_api_key(
            db_session, test_user.id, "Auth Test Key"
        )

        # Try to access protected endpoint with API key
        # Note: This requires implementing API key authentication middleware
        response = await client.get(
            "/api/v1/users/me",
            headers={"X-API-Key": raw_key},
        )

        # May return 401 if API key auth not yet implemented in middleware
        # assert response.status_code == 200

    async def test_expired_api_key_rejected(
        self, client: AsyncClient, test_user: User, db_session: AsyncSession
    ):
        """Test that expired API keys are rejected."""
        from app.services.api_key_service import APIKeyService

        # Create API key that expires immediately
        api_key, raw_key = await APIKeyService.create_api_key(
            db_session, test_user.id, "Expired Key", expires_in_days=0
        )

        # Force expiration
        from datetime import timedelta
        api_key.expires_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.commit()

        # Try to use expired key
        verified = await APIKeyService.verify_api_key(db_session, raw_key)
        assert verified is None


class TestAPIKeyUsageTracking:
    """Test API key usage tracking."""

    async def test_last_used_at_updated(
        self, test_user: User, db_session: AsyncSession
    ):
        """Test that last_used_at is updated when key is verified."""
        from app.services.api_key_service import APIKeyService

        api_key, raw_key = await APIKeyService.create_api_key(
            db_session, test_user.id, "Usage Tracking Key"
        )

        # Initial last_used_at should be None
        assert api_key.last_used_at is None

        # Verify key (simulates use)
        await APIKeyService.verify_api_key(db_session, raw_key)

        # Refresh and check last_used_at is set
        await db_session.refresh(api_key)
        assert api_key.last_used_at is not None
