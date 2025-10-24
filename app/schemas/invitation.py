"""Invitation schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class InvitationCreate(BaseModel):
    """Schema for creating an invitation."""

    email: EmailStr = Field(description="Email address to invite")
    expires_in_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days until invitation expires (1-30, default: 7)",
    )


class InvitationBase(BaseModel):
    """Base invitation schema."""

    id: UUID
    organization_id: UUID
    email: str
    is_accepted: bool
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitationResponse(InvitationBase):
    """Schema for invitation responses."""

    inviter_id: UUID
    accepted_at: datetime | None = None
    accepted_by_id: UUID | None = None


class InvitationDetailResponse(InvitationResponse):
    """Detailed invitation response with related objects."""

    organization_name: str | None = None
    inviter_email: str | None = None
    inviter_name: str | None = None


class InvitationCreateResponse(InvitationResponse):
    """Schema for invitation creation response (includes token)."""

    token: str = Field(description="Invitation token - share this with the invitee")


class InvitationListResponse(BaseModel):
    """Paginated invitation list response."""

    items: list[InvitationResponse]
    total: int
    page: int = 1
    page_size: int = 100
    pages: int = 1


class InvitationAcceptRequest(BaseModel):
    """Schema for accepting an invitation."""

    token: str = Field(description="Invitation token received via email or link")


class InvitationAcceptResponse(BaseModel):
    """Schema for invitation acceptance response."""

    message: str
    organization_id: UUID
    organization_name: str
