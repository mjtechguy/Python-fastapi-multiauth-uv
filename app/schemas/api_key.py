"""API Key schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    """Schema for API key creation."""

    name: str = Field(min_length=1, max_length=255)
    expires_at: datetime | None = None


class APIKeyResponse(BaseModel):
    """Schema for API key responses."""

    id: UUID
    name: str
    prefix: str
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreateResponse(APIKeyResponse):
    """Schema for API key creation response (includes full key)."""

    key: str


class APIKeyListResponse(BaseModel):
    """Paginated API key list response."""

    items: list[APIKeyResponse]
    total: int
    page: int
    page_size: int
    pages: int
