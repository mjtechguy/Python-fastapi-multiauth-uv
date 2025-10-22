"""API Key model for programmatic access."""

import secrets
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User


class APIKey(Base):
    """API Key for programmatic access."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Key details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)  # First chars for identification

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, key_hash, prefix)
        """
        key = secrets.token_urlsafe(32)
        prefix = key[:8]
        # In production, hash this properly
        from app.core.security import get_password_hash

        key_hash = get_password_hash(key)
        return key, key_hash, prefix

    def __repr__(self) -> str:
        return f"<APIKey {self.name} ({self.prefix}...)>"
