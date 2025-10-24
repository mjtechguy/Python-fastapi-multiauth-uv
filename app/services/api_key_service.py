"""Service for managing API keys."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.api_key import APIKey
from app.models.user import User


class APIKeyService:
    """Service for API key management."""

    @staticmethod
    async def create_api_key(
        db: AsyncSession, user_id: UUID, name: str, expires_in_days: int | None = None
    ) -> tuple[APIKey, str]:
        """
        Create a new API key for a user.

        Args:
            db: Database session
            user_id: User ID
            name: Name/description of the API key
            expires_in_days: Optional expiration in days (None = no expiration)

        Returns:
            Tuple of (APIKey object, raw_key_string)

        Note:
            The raw key is only returned once! Store it securely.
        """
        # Generate key
        raw_key, key_hash, prefix = APIKey.generate_key()

        # Calculate expiration
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        # Create API key record
        api_key = APIKey(
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            prefix=prefix,
            expires_at=expires_at,
            is_active=True,
        )

        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)

        return api_key, raw_key

    @staticmethod
    async def verify_api_key(db: AsyncSession, raw_key: str) -> APIKey | None:
        """
        Verify an API key and return the associated key object.

        Args:
            db: Database session
            raw_key: Raw API key string

        Returns:
            APIKey object if valid, None if invalid/expired
        """
        # Get prefix from raw key
        prefix = raw_key[:8]

        # Find key by prefix
        result = await db.execute(
            select(APIKey).where(
                APIKey.prefix == prefix, APIKey.is_active == True  # noqa: E712
            )
        )
        api_key = result.scalar_one_or_none()

        if not api_key:
            return None

        # Verify key hash
        if not verify_password(raw_key, api_key.key_hash):
            return None

        # Check expiration
        if api_key.expires_at and datetime.now(UTC) > api_key.expires_at:
            return None

        # Update last used timestamp
        api_key.last_used_at = datetime.now(UTC)
        await db.commit()

        return api_key

    @staticmethod
    async def get_user_api_keys(
        db: AsyncSession, user_id: UUID, include_inactive: bool = False
    ) -> list[APIKey]:
        """
        Get all API keys for a user.

        Args:
            db: Database session
            user_id: User ID
            include_inactive: Include inactive/revoked keys

        Returns:
            List of API keys
        """
        query = select(APIKey).where(APIKey.user_id == user_id)

        if not include_inactive:
            query = query.where(APIKey.is_active == True)  # noqa: E712

        result = await db.execute(query.order_by(APIKey.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_api_key_by_id(
        db: AsyncSession, key_id: UUID, user_id: UUID
    ) -> APIKey | None:
        """
        Get an API key by ID (ensures it belongs to the user).

        Args:
            db: Database session
            key_id: API key ID
            user_id: User ID (for authorization)

        Returns:
            APIKey object or None
        """
        result = await db.execute(
            select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def revoke_api_key(db: AsyncSession, key_id: UUID, user_id: UUID) -> bool:
        """
        Revoke (deactivate) an API key.

        Args:
            db: Database session
            key_id: API key ID
            user_id: User ID (for authorization)

        Returns:
            True if revoked, False if not found
        """
        api_key = await APIKeyService.get_api_key_by_id(db, key_id, user_id)

        if not api_key:
            return False

        api_key.is_active = False
        await db.commit()
        return True

    @staticmethod
    async def delete_api_key(db: AsyncSession, key_id: UUID, user_id: UUID) -> bool:
        """
        Permanently delete an API key.

        Args:
            db: Database session
            key_id: API key ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        api_key = await APIKeyService.get_api_key_by_id(db, key_id, user_id)

        if not api_key:
            return False

        await db.delete(api_key)
        await db.commit()
        return True

    @staticmethod
    async def get_user_from_api_key(db: AsyncSession, raw_key: str) -> User | None:
        """
        Get the user associated with an API key.

        Args:
            db: Database session
            raw_key: Raw API key string

        Returns:
            User object if key is valid, None otherwise
        """
        api_key = await APIKeyService.verify_api_key(db, raw_key)

        if not api_key:
            return None

        # Get user
        result = await db.execute(select(User).where(User.id == api_key.user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def cleanup_expired_keys(db: AsyncSession) -> int:
        """
        Mark expired API keys as inactive.

        Args:
            db: Database session

        Returns:
            Number of keys marked inactive
        """
        now = datetime.now(UTC)

        result = await db.execute(
            select(APIKey).where(
                APIKey.expires_at < now, APIKey.is_active == True  # noqa: E712
            )
        )
        expired_keys = result.scalars().all()

        for key in expired_keys:
            key.is_active = False

        await db.commit()
        return len(expired_keys)
