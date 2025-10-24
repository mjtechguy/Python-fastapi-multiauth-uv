"""Invitation model for inviting users to organizations."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Invitation(Base):
    """Invitation model for organization invites."""

    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Organization relationship
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Inviter
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Invitee
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Invitation token
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)

    # Status
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    inviter: Mapped["User"] = relationship("User", foreign_keys=[inviter_id])
    accepted_by: Mapped["User | None"] = relationship("User", foreign_keys=[accepted_by_id])

    @staticmethod
    def generate_token() -> str:
        """Generate secure invitation token."""
        return secrets.token_urlsafe(32)

    @classmethod
    def create_invitation(
        cls,
        organization_id: uuid.UUID,
        inviter_id: uuid.UUID,
        email: str,
        expires_in_days: int = 7,
    ) -> "Invitation":
        """Create a new invitation."""
        return cls(
            organization_id=organization_id,
            inviter_id=inviter_id,
            email=email,
            token=cls.generate_token(),
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        )

    def is_valid(self) -> bool:
        """Check if invitation is still valid."""
        return (
            not self.is_accepted
            and self.expires_at > datetime.now(UTC)
        )

    def __repr__(self) -> str:
        return f"<Invitation {self.email} to org {self.organization_id}>"
