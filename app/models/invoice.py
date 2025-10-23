"""Invoice models for billing."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.subscription import Subscription


class Invoice(Base):
    """Invoice model tracking billing invoices from Stripe."""

    __tablename__ = "invoices"

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

    # Stripe IDs
    stripe_invoice_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    # Invoice Details
    invoice_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # draft, open, paid, void, uncollectible

    # Amounts (in cents)
    amount_due: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    subtotal: Mapped[int] = mapped_column(Integer, nullable=False)
    tax: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")

    # URLs
    invoice_pdf: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Billing
    billing_reason: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # subscription_create, subscription_cycle, manual

    # Dates
    period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata (using stripe_metadata to avoid SQLAlchemy reserved word)
    stripe_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="invoices"
    )
    subscription: Mapped["Subscription | None"] = relationship(
        "Subscription", back_populates="invoices"
    )

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number or self.id} - {self.status}>"

    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid."""
        return self.status == "paid"

    @property
    def is_open(self) -> bool:
        """Check if invoice is open (unpaid)."""
        return self.status == "open"

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue."""
        if not self.due_date or self.is_paid:
            return False
        return self.due_date < datetime.now(timezone.utc)

    @property
    def amount_due_dollars(self) -> float:
        """Get amount due in dollars."""
        return self.amount_due / 100.0

    @property
    def amount_paid_dollars(self) -> float:
        """Get amount paid in dollars."""
        return self.amount_paid / 100.0

    @property
    def total_dollars(self) -> float:
        """Get total in dollars."""
        return self.total / 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "subscription_id": str(self.subscription_id) if self.subscription_id else None,
            "stripe_invoice_id": self.stripe_invoice_id,
            "invoice_number": self.invoice_number,
            "status": self.status,
            "amount_due": self.amount_due_dollars,
            "amount_paid": self.amount_paid_dollars,
            "amount_remaining": self.amount_remaining / 100.0,
            "subtotal": self.subtotal / 100.0,
            "tax": self.tax / 100.0,
            "total": self.total_dollars,
            "currency": self.currency,
            "invoice_pdf": self.invoice_pdf,
            "hosted_invoice_url": self.hosted_invoice_url,
            "billing_reason": self.billing_reason,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "is_paid": self.is_paid,
            "is_overdue": self.is_overdue,
            "metadata": self.stripe_metadata,
            "created_at": self.created_at.isoformat(),
        }
