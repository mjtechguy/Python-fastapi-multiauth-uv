"""TOTP (Time-based One-Time Password) model for 2FA."""

import secrets
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User


class TOTPSecret(Base):
    """TOTP secret for two-factor authentication."""

    __tablename__ = "totp_secrets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # TOTP secret (encrypted in production)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)

    # Backup codes (hashed)
    backup_codes: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Device info
    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="totp_secret")

    @staticmethod
    def generate_backup_codes(count: int = 10) -> list[str]:
        """Generate backup codes for account recovery."""
        return [secrets.token_hex(4).upper() for _ in range(count)]

    def __repr__(self) -> str:
        return f"<TOTPSecret user_id={self.user_id} enabled={self.is_enabled}>"
