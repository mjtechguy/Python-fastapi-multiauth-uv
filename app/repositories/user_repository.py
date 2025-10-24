"""User repository for data access."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model."""

    def __init__(self, db: AsyncSession):
        """Initialize user repository."""
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles), selectinload(User.organizations))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_with_relationships(self, user_id: UUID) -> User | None:
        """Get user with all relationships loaded."""
        result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.roles),
                selectinload(User.organizations),
                selectinload(User.teams),
                selectinload(User.oauth_accounts),
            )
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Get all active users."""
        result = await self.db.execute(
            select(User).where(User.is_active).offset(skip).limit(limit)
        )
        return list(result.scalars().all())
