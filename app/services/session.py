"""Session management service."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from user_agents import parse as parse_user_agent

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.session import UserSession
from app.models.user import User


class SessionService:
    """Service for managing user sessions."""

    @staticmethod
    def parse_user_agent(user_agent_string: str) -> dict:
        """
        Parse user agent string to extract device information.

        Args:
            user_agent_string: User agent string from request

        Returns:
            Dictionary with device information
        """
        ua = parse_user_agent(user_agent_string)

        return {
            "device_type": "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop",
            "device_name": f"{ua.device.brand} {ua.device.model}" if ua.device.brand else None,
            "os_name": ua.os.family,
            "os_version": ua.os.version_string,
            "browser_name": ua.browser.family,
            "browser_version": ua.browser.version_string,
        }

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user: User,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        """
        Create a new session.

        Args:
            db: Database session
            user: User to create session for
            refresh_token: Refresh token for this session
            user_agent: User agent string
            ip_address: IP address

        Returns:
            Created session
        """
        # Hash the refresh token
        token_hash = get_password_hash(refresh_token)

        # Parse user agent
        device_info = {}
        if user_agent:
            device_info = SessionService.parse_user_agent(user_agent)

        # Calculate expiration
        expires_at = datetime.now(UTC) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        # Create session
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            **device_info,
        )

        db.add(session)
        await db.flush()
        await db.refresh(session)

        return session

    @staticmethod
    async def get_session_by_token(
        db: AsyncSession, refresh_token: str
    ) -> UserSession | None:
        """
        Get session by refresh token.

        Args:
            db: Database session
            refresh_token: Refresh token

        Returns:
            Session if found and valid
        """
        # Hash the token to compare
        token_hash = get_password_hash(refresh_token)

        result = await db.execute(
            select(UserSession).where(
                UserSession.token_hash == token_hash,
                UserSession.is_active,
                not UserSession.revoked,
            )
        )
        session = result.scalar_one_or_none()

        if session and session.is_valid:
            # Update last activity
            session.last_activity = datetime.now(UTC)
            await db.flush()
            return session

        return None

    @staticmethod
    async def get_user_sessions(
        db: AsyncSession, user_id: UUID, include_expired: bool = False
    ) -> list[UserSession]:
        """
        Get all sessions for a user.

        Args:
            db: Database session
            user_id: User ID
            include_expired: Whether to include expired sessions

        Returns:
            List of sessions
        """
        query = select(UserSession).where(UserSession.user_id == user_id)

        if not include_expired:
            query = query.where(
                UserSession.is_active,
                not UserSession.revoked,
            )

        result = await db.execute(query.order_by(UserSession.last_activity.desc()))
        sessions = result.scalars().all()

        # Filter out expired sessions if not including them
        if not include_expired:
            sessions = [s for s in sessions if not s.is_expired]

        return list(sessions)

    @staticmethod
    async def revoke_session(db: AsyncSession, session_id: UUID) -> bool:
        """
        Revoke a specific session.

        Args:
            db: Database session
            session_id: Session ID to revoke

        Returns:
            True if session was revoked
        """
        result = await db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session:
            return False

        session.revoked = True
        session.revoked_at = datetime.now(UTC)
        session.is_active = False
        await db.flush()

        return True

    @staticmethod
    async def revoke_all_user_sessions(
        db: AsyncSession, user_id: UUID, except_session_id: UUID | None = None
    ) -> int:
        """
        Revoke all sessions for a user.

        Args:
            db: Database session
            user_id: User ID
            except_session_id: Optional session ID to keep active

        Returns:
            Number of sessions revoked
        """
        query = select(UserSession).where(
            UserSession.user_id == user_id,
            UserSession.is_active,
            not UserSession.revoked,
        )

        if except_session_id:
            query = query.where(UserSession.id != except_session_id)

        result = await db.execute(query)
        sessions = result.scalars().all()

        revoked_count = 0
        for session in sessions:
            session.revoked = True
            session.revoked_at = datetime.now(UTC)
            session.is_active = False
            revoked_count += 1

        await db.flush()
        return revoked_count

    @staticmethod
    async def cleanup_expired_sessions(db: AsyncSession) -> int:
        """
        Clean up expired and revoked sessions.

        Args:
            db: Database session

        Returns:
            Number of sessions deleted
        """
        # Delete sessions that are either:
        # 1. Expired for more than 7 days
        # 2. Revoked for more than 30 days
        cutoff_expired = datetime.now(UTC) - timedelta(days=7)
        cutoff_revoked = datetime.now(UTC) - timedelta(days=30)

        result = await db.execute(
            delete(UserSession).where(
                (UserSession.expires_at < cutoff_expired)
                | (
                    (UserSession.revoked)
                    & (UserSession.revoked_at < cutoff_revoked)
                )
            )
        )

        await db.flush()
        return result.rowcount  # type: ignore

    @staticmethod
    async def get_session_count(db: AsyncSession, user_id: UUID) -> dict:
        """
        Get session statistics for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dictionary with session counts
        """
        from sqlalchemy import Integer, func

        # Get all sessions
        result = await db.execute(
            select(
                func.count(UserSession.id).label("total"),
                func.sum(
                    func.cast(UserSession.is_active & ~UserSession.revoked, Integer)
                ).label("active"),
            ).where(UserSession.user_id == user_id)
        )

        row = result.one()

        active_sessions = await SessionService.get_user_sessions(db, user_id)

        return {
            "total": row.total,
            "active": len([s for s in active_sessions if s.is_valid]),
            "devices": len({s.device_type for s in active_sessions if s.device_type}),
        }
