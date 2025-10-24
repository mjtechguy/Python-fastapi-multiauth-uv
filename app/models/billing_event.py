"""Billing event models for audit logging."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.subscription import Subscription


class BillingEvent(Base):
    """Billing event model for audit logging of billing-related events."""

    __tablename__ = "billing_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign Keys
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Event Details
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # subscription.created, payment.succeeded, etc.
    stripe_event_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )

    # Event Data
    event_data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Processing Status
    processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="billing_events"
    )
    subscription: Mapped["Subscription | None"] = relationship("Subscription")

    def __repr__(self) -> str:
        return f"<BillingEvent {self.event_type} - {'Processed' if self.processed else 'Pending'}>"

    def mark_processed(self) -> None:
        """Mark event as processed."""
        self.processed = True
        self.processed_at = datetime.now(UTC)

    def mark_failed(self, error: str) -> None:
        """Mark event as failed with error message."""
        self.error_message = error
        self.processed = False

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "subscription_id": str(self.subscription_id) if self.subscription_id else None,
            "event_type": self.event_type,
            "stripe_event_id": self.stripe_event_id,
            "event_data": self.event_data,
            "processed": self.processed,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }
