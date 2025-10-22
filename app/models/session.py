"""User session model for session management."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserSession(Base):
    """User session for tracking active sessions and devices."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Session token (hashed refresh token)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Device information
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # mobile, desktop, tablet
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    browser_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    browser_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Location information
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # User agent
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Session status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    last_activity: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    @property
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return self.expires_at < datetime.now(timezone.utc)

    @property
    def is_valid(self) -> bool:
        """Check if session is valid (active, not revoked, not expired)."""
        return self.is_active and not self.revoked and not self.is_expired

    def __repr__(self) -> str:
        return f"<UserSession {self.device_name} - {self.user_id}>"
