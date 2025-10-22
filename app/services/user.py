"""User service for user management operations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Service for user management operations."""

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
        """Get user by ID."""
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles), selectinload(User.organizations))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """Get user by email."""
        result = await db.execute(
            select(User)
            .options(selectinload(User.roles), selectinload(User.organizations))
            .where(User.email == email)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> User | None:
        """Get user by username."""
        result = await db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create(db: AsyncSession, user_in: UserCreate) -> User:
        """Create a new user."""
        user = User(
            email=user_in.email,
            username=user_in.username,
            full_name=user_in.full_name,
            hashed_password=get_password_hash(user_in.password),
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def update(db: AsyncSession, user: User, user_in: UserUpdate) -> User:
        """Update user information."""
        update_data = user_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_password(db: AsyncSession, user: User, new_password: str) -> User:
        """Update user password."""
        user.hashed_password = get_password_hash(new_password)
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def verify_password(user: User, password: str) -> bool:
        """Verify user password."""
        if not user.hashed_password:
            return False
        return verify_password(password, user.hashed_password)

    @staticmethod
    async def update_last_login(db: AsyncSession, user: User) -> None:
        """Update user's last login timestamp."""
        user.last_login = datetime.now(timezone.utc)
        user.failed_login_attempts = 0
        user.locked_until = None
        await db.flush()

    @staticmethod
    async def increment_failed_login(db: AsyncSession, user: User) -> None:
        """Increment failed login attempts."""
        from app.core.config import settings

        user.failed_login_attempts += 1

        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            from datetime import timedelta

            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.LOCKOUT_DURATION_MINUTES
            )

        await db.flush()

    @staticmethod
    async def is_locked(user: User) -> bool:
        """Check if user account is locked."""
        if user.locked_until is None:
            return False

        if user.locked_until > datetime.now(timezone.utc):
            return True

        return False

    @staticmethod
    async def list_users(
        db: AsyncSession, skip: int = 0, limit: int = 100, is_superuser: bool | None = None
    ) -> tuple[list[User], int]:
        """List users with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            is_superuser: Filter by superuser status (None = no filter)

        Returns:
            Tuple of (users list, total count)
        """
        # Build base query
        query = select(User).options(selectinload(User.roles))
        count_query = select(func.count(User.id))

        # Apply superuser filter if specified
        if is_superuser is not None:
            query = query.where(User.is_superuser == is_superuser)
            count_query = count_query.where(User.is_superuser == is_superuser)

        # Get total count
        count_result = await db.execute(count_query)
        total = count_result.scalar_one()

        # Get paginated results
        result = await db.execute(query.offset(skip).limit(limit))
        users = result.scalars().all()

        return list(users), total

    @staticmethod
    async def activate(db: AsyncSession, user: User) -> User:
        """Activate user account."""
        user.is_active = True
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def deactivate(db: AsyncSession, user: User) -> User:
        """Deactivate user account."""
        user.is_active = False
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def verify_email(db: AsyncSession, user: User) -> User:
        """Verify user email."""
        user.is_verified = True
        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def delete(db: AsyncSession, user: User) -> None:
        """Delete user (soft delete by deactivating)."""
        user.is_active = False
        await db.flush()
