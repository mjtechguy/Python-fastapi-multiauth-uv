"""Feature flag service for managing feature flags."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_flag import FeatureFlag
from app.services.cache import cache


class FeatureFlagService:
    """Service for feature flag operations."""

    CACHE_EXPIRE = 300  # 5 minutes

    @staticmethod
    async def is_enabled(
        db: AsyncSession,
        flag_name: str,
        user_id: UUID | None = None,
        user_email: str | None = None,
    ) -> bool:
        """
        Check if a feature flag is enabled.

        Args:
            db: Database session
            flag_name: Name of the feature flag
            user_id: Optional user ID for targeting
            user_email: Optional user email for targeting

        Returns:
            True if feature is enabled
        """
        # Try cache first
        cache_key = f"feature_flag:{flag_name}"
        cached_flag = await cache.get(cache_key)

        if cached_flag is None:
            # Get from database
            result = await db.execute(
                select(FeatureFlag).where(FeatureFlag.name == flag_name)
            )
            flag = result.scalar_one_or_none()

            if not flag:
                return False

            # Cache the flag
            await cache.set(
                cache_key,
                {
                    "is_enabled": flag.is_enabled,
                    "rollout_percentage": flag.rollout_percentage,
                    "targeting_rules": flag.targeting_rules,
                },
                expire=FeatureFlagService.CACHE_EXPIRE,
            )
        else:
            # Reconstruct flag from cache
            flag = FeatureFlag(
                name=flag_name,
                is_enabled=cached_flag["is_enabled"],
                rollout_percentage=cached_flag["rollout_percentage"],
                targeting_rules=cached_flag["targeting_rules"],
            )

        # Check if enabled for user
        if user_id and user_email:
            return flag.is_enabled_for_user(user_id, user_email)

        return flag.is_enabled

    @staticmethod
    async def create_flag(
        db: AsyncSession,
        name: str,
        description: str | None = None,
        is_enabled: bool = False,
    ) -> FeatureFlag:
        """Create a new feature flag."""
        flag = FeatureFlag(
            name=name,
            description=description,
            is_enabled=is_enabled,
        )
        db.add(flag)
        await db.flush()
        await db.refresh(flag)

        # Invalidate cache
        await cache.delete(f"feature_flag:{name}")

        return flag

    @staticmethod
    async def update_flag(
        db: AsyncSession,
        flag: FeatureFlag,
        is_enabled: bool | None = None,
        rollout_percentage: float | None = None,
    ) -> FeatureFlag:
        """Update feature flag."""
        if is_enabled is not None:
            flag.is_enabled = is_enabled

        if rollout_percentage is not None:
            flag.rollout_percentage = max(0.0, min(1.0, rollout_percentage))

        await db.flush()
        await db.refresh(flag)

        # Invalidate cache
        await cache.delete(f"feature_flag:{flag.name}")

        return flag

    @staticmethod
    async def delete_flag(db: AsyncSession, flag: FeatureFlag) -> None:
        """Delete feature flag."""
        flag_name = flag.name
        await db.delete(flag)
        await db.flush()

        # Invalidate cache
        await cache.delete(f"feature_flag:{flag_name}")
