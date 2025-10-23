"""Payment method models for billing."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class PaymentMethod(Base):
    """Payment method model for storing customer payment methods."""

    __tablename__ = "payment_methods"

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

    # Stripe ID
    stripe_payment_method_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Payment Method Details
    type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # card, us_bank_account, sepa_debit

    # Card Details (if type=card)
    card_brand: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # visa, mastercard, amex
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    card_exp_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    card_exp_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    card_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Bank Account Details (if type=us_bank_account)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)

    # Status
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

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
        "Organization", back_populates="payment_methods"
    )

    def __repr__(self) -> str:
        return f"<PaymentMethod {self.type} ending in {self.card_last4 or self.bank_last4}>"

    @property
    def display_name(self) -> str:
        """Get display name for payment method."""
        if self.type == "card":
            brand = self.card_brand.capitalize() if self.card_brand else "Card"
            return f"{brand} ending in {self.card_last4}"
        elif self.type == "us_bank_account":
            return f"{self.bank_name or 'Bank'} ending in {self.bank_last4}"
        else:
            return self.type.replace("_", " ").title()

    @property
    def is_expired(self) -> bool:
        """Check if card is expired (only for cards)."""
        if self.type != "card" or not self.card_exp_month or not self.card_exp_year:
            return False

        now = datetime.now(timezone.utc)
        # Card expires at end of expiration month
        return (
            self.card_exp_year < now.year
            or (self.card_exp_year == now.year and self.card_exp_month < now.month)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "stripe_payment_method_id": self.stripe_payment_method_id,
            "type": self.type,
            "display_name": self.display_name,
            "card_brand": self.card_brand,
            "card_last4": self.card_last4,
            "card_exp_month": self.card_exp_month,
            "card_exp_year": self.card_exp_year,
            "bank_name": self.bank_name,
            "bank_last4": self.bank_last4,
            "is_default": self.is_default,
            "is_expired": self.is_expired,
            "created_at": self.created_at.isoformat(),
        }
