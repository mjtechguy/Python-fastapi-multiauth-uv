"""Subscription models for billing."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.invoice import Invoice
    from app.models.organization import Organization
    from app.models.subscription_plan import SubscriptionPlan


class Subscription(Base):
    """Subscription model tracking organization subscriptions."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign Keys
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscription_plans.id"),
        index=True,
        nullable=False,
    )

    # Stripe IDs
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # Status: active, trialing, past_due, canceled, unpaid, incomplete, incomplete_expired
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active", index=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Billing Period
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Trial Period
    trial_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Metadata (using stripe_metadata to avoid SQLAlchemy reserved word)
    stripe_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="subscription"
    )
    plan: Mapped["SubscriptionPlan"] = relationship(
        "SubscriptionPlan", back_populates="subscriptions"
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Subscription {self.id} - {self.status}>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is active (including trial)."""
        return self.status in ["active", "trialing"]

    @property
    def is_trialing(self) -> bool:
        """Check if subscription is in trial period."""
        if not self.trial_end:
            return False
        return (
            self.status == "trialing"
            and self.trial_end > datetime.now(UTC)
        )

    @property
    def is_past_due(self) -> bool:
        """Check if subscription payment is past due."""
        return self.status == "past_due"

    @property
    def is_canceled(self) -> bool:
        """Check if subscription is canceled."""
        return self.status == "canceled"

    @property
    def will_cancel_at_period_end(self) -> bool:
        """Check if subscription will cancel at end of period."""
        return self.cancel_at_period_end and self.is_active

    @property
    def days_until_renewal(self) -> int:
        """Get days until next renewal."""
        if not self.current_period_end:
            return 0
        delta = self.current_period_end - datetime.now(UTC)
        return max(0, delta.days)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "plan_id": str(self.plan_id),
            "stripe_subscription_id": self.stripe_subscription_id,
            "stripe_customer_id": self.stripe_customer_id,
            "status": self.status,
            "cancel_at_period_end": self.cancel_at_period_end,
            "canceled_at": self.canceled_at.isoformat() if self.canceled_at else None,
            "current_period_start": self.current_period_start.isoformat(),
            "current_period_end": self.current_period_end.isoformat(),
            "trial_start": self.trial_start.isoformat() if self.trial_start else None,
            "trial_end": self.trial_end.isoformat() if self.trial_end else None,
            "is_active": self.is_active,
            "is_trialing": self.is_trialing,
            "days_until_renewal": self.days_until_renewal,
            "metadata": self.stripe_metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
