"""Usage quota models for SaaS monetization."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class OrganizationQuota(Base):
    """Organization usage quotas and limits."""

    __tablename__ = "organization_quotas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, index=True
    )

    # User limits
    max_users: Mapped[int] = mapped_column(default=10)
    current_users: Mapped[int] = mapped_column(default=0, index=True)

    # Storage limits (in bytes)
    max_storage_bytes: Mapped[int] = mapped_column(BigInteger, default=1_073_741_824)  # 1GB
    current_storage_bytes: Mapped[int] = mapped_column(BigInteger, default=0, index=True)

    # API call limits (per month)
    max_api_calls_per_month: Mapped[int] = mapped_column(default=10000)
    current_api_calls_this_month: Mapped[int] = mapped_column(default=0, index=True)

    # File upload limits
    max_file_uploads_per_day: Mapped[int] = mapped_column(default=100)
    current_file_uploads_today: Mapped[int] = mapped_column(default=0, index=True)
    max_file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=10_485_760)  # 10MB

    # Tracking timestamps
    api_calls_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    file_uploads_reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="quota")

    def is_user_quota_exceeded(self) -> bool:
        """Check if user quota is exceeded."""
        return self.current_users >= self.max_users

    def is_storage_quota_exceeded(self, additional_bytes: int = 0) -> bool:
        """Check if storage quota is exceeded."""
        return (self.current_storage_bytes + additional_bytes) > self.max_storage_bytes

    def is_api_call_quota_exceeded(self) -> bool:
        """Check if API call quota is exceeded."""
        return self.current_api_calls_this_month >= self.max_api_calls_per_month

    def is_file_upload_quota_exceeded(self) -> bool:
        """Check if file upload quota is exceeded."""
        return self.current_file_uploads_today >= self.max_file_uploads_per_day

    def is_file_size_exceeded(self, file_size_bytes: int) -> bool:
        """Check if file size exceeds limit."""
        return file_size_bytes > self.max_file_size_bytes

    def get_usage_percentage(self, quota_type: str) -> float:
        """Get usage percentage for a specific quota type."""
        if quota_type == "users":
            return (self.current_users / self.max_users * 100) if self.max_users > 0 else 0
        if quota_type == "storage":
            return (
                (self.current_storage_bytes / self.max_storage_bytes * 100)
                if self.max_storage_bytes > 0
                else 0
            )
        if quota_type == "api_calls":
            return (
                (self.current_api_calls_this_month / self.max_api_calls_per_month * 100)
                if self.max_api_calls_per_month > 0
                else 0
            )
        if quota_type == "file_uploads":
            return (
                (self.current_file_uploads_today / self.max_file_uploads_per_day * 100)
                if self.max_file_uploads_per_day > 0
                else 0
            )
        return 0.0


class UsageLog(Base):
    """Detailed usage tracking for auditing and analytics."""

    __tablename__ = "usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Usage type: api_call, file_upload, storage_add, storage_remove, user_add, user_remove
    usage_type: Mapped[str] = mapped_column(String(50), index=True)

    # Additional extra data
    extra_data: Mapped[dict | None] = mapped_column(JSONB, default=None, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
