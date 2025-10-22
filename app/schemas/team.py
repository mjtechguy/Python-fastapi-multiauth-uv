"""Team schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TeamBase(BaseModel):
    """Base team schema."""

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class TeamCreate(TeamBase):
    """Schema for team creation."""

    organization_id: UUID


class TeamUpdate(BaseModel):
    """Schema for team updates."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class TeamResponse(TeamBase):
    """Schema for team responses."""

    id: UUID
    organization_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TeamWithMembers(TeamResponse):
    """Team response with member count."""

    member_count: int = 0


class TeamListResponse(BaseModel):
    """Paginated team list response."""

    items: list[TeamResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AddTeamMemberRequest(BaseModel):
    """Schema for adding members to team."""

    user_id: UUID


class RemoveTeamMemberRequest(BaseModel):
    """Schema for removing members from team."""

    user_id: UUID
