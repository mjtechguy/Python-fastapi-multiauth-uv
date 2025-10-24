"""Quota schemas for API validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QuotaLimits(BaseModel):
    """Quota limits configuration."""

    max_users: int = Field(default=10, ge=1, description="Maximum number of users")
    max_storage_bytes: int = Field(
        default=1_073_741_824, ge=0, description="Maximum storage in bytes (default 1GB)"
    )
    max_api_calls_per_month: int = Field(
        default=10000, ge=0, description="Maximum API calls per month"
    )
    max_file_uploads_per_day: int = Field(
        default=100, ge=0, description="Maximum file uploads per day"
    )
    max_file_size_bytes: int = Field(
        default=10_485_760, ge=0, description="Maximum file size in bytes (default 10MB)"
    )


class QuotaUsage(BaseModel):
    """Current quota usage."""

    current_users: int = Field(..., description="Current number of users")
    current_storage_bytes: int = Field(..., description="Current storage usage in bytes")
    current_api_calls_this_month: int = Field(..., description="Current API calls this month")
    current_file_uploads_today: int = Field(..., description="Current file uploads today")


class QuotaStatus(BaseModel):
    """Combined quota limits, usage, and status."""

    organization_id: uuid.UUID
    limits: QuotaLimits
    usage: QuotaUsage
    usage_percentages: dict[str, float] = Field(
        ..., description="Usage percentages for each quota type"
    )
    api_calls_reset_at: datetime = Field(..., description="When API call quota resets")
    file_uploads_reset_at: datetime = Field(..., description="When file upload quota resets")
    last_updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateQuotaLimitsRequest(BaseModel):
    """Request to update quota limits."""

    max_users: int | None = Field(None, ge=1, description="Maximum number of users")
    max_storage_bytes: int | None = Field(None, ge=0, description="Maximum storage in bytes")
    max_api_calls_per_month: int | None = Field(None, ge=0, description="Maximum API calls per month")
    max_file_uploads_per_day: int | None = Field(None, ge=0, description="Maximum file uploads per day")
    max_file_size_bytes: int | None = Field(None, ge=0, description="Maximum file size in bytes")


class UpdateQuotaLimitsResponse(BaseModel):
    """Response after updating quota limits."""

    message: str
    quota: QuotaStatus


class UsageLogEntry(BaseModel):
    """Usage log entry for analytics."""

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID | None
    usage_type: str = Field(..., description="Type: api_call, file_upload, storage_add, etc.")
    metadata: dict | None = Field(None, description="Additional metadata about the usage")
    created_at: datetime

    class Config:
        from_attributes = True


class UsageLogListResponse(BaseModel):
    """Paginated usage log response."""

    logs: list[UsageLogEntry]
    total: int
    page: int
    page_size: int
