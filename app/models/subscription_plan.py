"""Subscription plan models for billing."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.subscription import Subscription


class SubscriptionPlan(Base):
    """Subscription plan model defining pricing tiers."""

    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Plan Identification
    name: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=False
    )  # free, starter, pro, enterprise
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stripe IDs (NULL for free tier)
    stripe_price_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    stripe_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pricing (stored in dollars, converted to cents for Stripe)
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    price_yearly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0.00")
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")

    # Quota Limits (-1 means unlimited)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_storage_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1_073_741_824
    )  # 1GB
    max_api_calls_per_month: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10000
    )
    max_file_uploads_per_day: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100
    )
    max_file_size_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=10_485_760
    )  # 10MB

    # Features (JSON object)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Ordering & Display
    tier_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )  # 0=free, 1=starter, 2=pro, 3=enterprise
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="plan"
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan {self.display_name}>"

    @property
    def is_free(self) -> bool:
        """Check if this is the free tier."""
        return self.name == "free" or self.price_monthly == 0

    @property
    def has_unlimited_users(self) -> bool:
        """Check if plan has unlimited users."""
        return self.max_users == -1

    @property
    def has_unlimited_storage(self) -> bool:
        """Check if plan has unlimited storage."""
        return self.max_storage_bytes == -1

    @property
    def has_unlimited_api_calls(self) -> bool:
        """Check if plan has unlimited API calls."""
        return self.max_api_calls_per_month == -1

    def get_feature(self, feature_name: str) -> bool:
        """Get feature flag value."""
        return self.features.get(feature_name, False)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "price_monthly": float(self.price_monthly),
            "price_yearly": float(self.price_yearly),
            "currency": self.currency,
            "max_users": self.max_users,
            "max_storage_bytes": self.max_storage_bytes,
            "max_api_calls_per_month": self.max_api_calls_per_month,
            "max_file_uploads_per_day": self.max_file_uploads_per_day,
            "max_file_size_bytes": self.max_file_size_bytes,
            "features": self.features,
            "tier_level": self.tier_level,
            "is_featured": self.is_featured,
        }
