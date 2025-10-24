"""Audit log model for security and compliance."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base):
    """Audit log for tracking all sensitive operations."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # User who performed the action (nullable for system actions)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g., 'user.login'
    resource_type: Mapped[str] = mapped_column(String(100), nullable=True, index=True)  # e.g., 'user'
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True)

    # Request details
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Additional context
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failure, error

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    # Relationships
    user: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id}>"
