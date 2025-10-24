"""Organization schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationBase(BaseModel):
    """Base organization schema."""

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = None


class OrganizationCreate(OrganizationBase):
    """Schema for organization creation."""



class OrganizationUpdate(BaseModel):
    """Schema for organization updates."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    settings: dict | None = None


class OrganizationResponse(OrganizationBase):
    """Schema for organization responses."""

    id: UUID
    owner_id: UUID
    is_active: bool
    settings: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrganizationWithMembers(OrganizationResponse):
    """Organization response with member count."""

    member_count: int = 0
    team_count: int = 0


class OrganizationListResponse(BaseModel):
    """Paginated organization list response."""

    items: list[OrganizationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AddMemberRequest(BaseModel):
    """Schema for adding members to organization."""

    user_id: UUID
    role_ids: list[UUID] = []


class RemoveMemberRequest(BaseModel):
    """Schema for removing members from organization."""

    user_id: UUID
