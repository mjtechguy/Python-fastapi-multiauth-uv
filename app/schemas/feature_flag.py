"""Feature flag schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FeatureFlagCreate(BaseModel):
    """Schema for creating a feature flag."""

    name: str = Field(min_length=1, max_length=100, description="Unique flag name")
    description: str | None = Field(None, description="Description of the feature")
    is_enabled: bool = Field(default=False, description="Whether the flag is enabled globally")
    rollout_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Percentage of users to enable (0.0 to 1.0)",
    )
    targeting_rules: dict = Field(
        default_factory=dict,
        description="Targeting rules for specific users/orgs",
    )


class FeatureFlagUpdate(BaseModel):
    """Schema for updating a feature flag."""

    description: str | None = None
    is_enabled: bool | None = None
    rollout_percentage: float | None = Field(None, ge=0.0, le=1.0)
    targeting_rules: dict | None = None


class FeatureFlagResponse(BaseModel):
    """Schema for feature flag responses."""

    id: UUID
    name: str
    description: str | None
    is_enabled: bool
    rollout_percentage: float
    targeting_rules: dict
    extra_data: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeatureFlagListResponse(BaseModel):
    """Paginated feature flag list response."""

    items: list[FeatureFlagResponse]
    total: int
    page: int = 1
    page_size: int = 100
    pages: int = 1


class FeatureFlagCheckRequest(BaseModel):
    """Schema for checking if a flag is enabled for a user."""

    flag_name: str = Field(description="Name of the feature flag to check")


class FeatureFlagCheckResponse(BaseModel):
    """Schema for feature flag check response."""

    flag_name: str
    is_enabled: bool
    message: str | None = None


class FeatureFlagTargetingUpdate(BaseModel):
    """Schema for updating targeting rules."""

    targeting_rules: dict = Field(
        description="Targeting rules (user_ids, organization_ids, user_emails)"
    )


class FeatureFlagBulkCheckRequest(BaseModel):
    """Schema for checking multiple flags at once."""

    flag_names: list[str] = Field(
        min_length=1,
        max_length=50,
        description="List of flag names to check",
    )


class FeatureFlagBulkCheckResponse(BaseModel):
    """Schema for bulk flag check response."""

    flags: dict[str, bool] = Field(
        description="Map of flag names to their enabled status"
    )
