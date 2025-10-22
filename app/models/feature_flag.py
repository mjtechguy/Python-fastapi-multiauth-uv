"""Feature flag model for gradual feature rollout."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FeatureFlag(Base):
    """Feature flag for controlling feature availability."""

    __tablename__ = "feature_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Flag details
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Rollout percentage (0.0 to 1.0)
    rollout_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Targeting rules (JSON)
    # Example: {"user_ids": [], "organization_ids": [], "user_emails": []}
    targeting_rules: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def is_enabled_for_user(self, user_id: uuid.UUID, user_email: str) -> bool:
        """
        Check if feature is enabled for a specific user.

        Args:
            user_id: User ID to check
            user_email: User email to check

        Returns:
            True if feature is enabled for this user
        """
        if not self.is_enabled:
            return False

        # Check if user is in targeting rules
        rules = self.targeting_rules
        if rules:
            # Check specific user IDs
            if "user_ids" in rules and str(user_id) in rules["user_ids"]:
                return True

            # Check specific emails
            if "user_emails" in rules and user_email in rules["user_emails"]:
                return True

        # Check rollout percentage (deterministic based on user ID)
        if self.rollout_percentage > 0:
            # Simple hash-based distribution
            user_hash = hash(str(user_id)) % 100 / 100.0
            return user_hash <= self.rollout_percentage

        return False

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.name}: {self.is_enabled}>"
