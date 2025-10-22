"""Session schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionResponse(BaseModel):
    """Response for session information."""

    id: UUID
    device_type: str | None
    device_name: str | None
    os_name: str | None
    os_version: str | None
    browser_name: str | None
    browser_version: str | None
    ip_address: str | None
    country: str | None
    city: str | None
    is_active: bool
    is_current: bool = False
    created_at: datetime
    last_activity: datetime
    expires_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Response for list of sessions."""

    sessions: list[SessionResponse]
    total: int
    active: int


class SessionStatsResponse(BaseModel):
    """Response for session statistics."""

    total: int
    active: int
    devices: int
