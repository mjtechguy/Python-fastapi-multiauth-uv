"""Role and Permission schemas for RBAC."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PermissionBase(BaseModel):
    """Base permission schema."""

    name: str = Field(min_length=1, max_length=100)
    resource: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=50)
    description: str | None = None


class PermissionCreate(PermissionBase):
    """Schema for permission creation."""



class PermissionResponse(PermissionBase):
    """Schema for permission responses."""

    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleBase(BaseModel):
    """Base role schema."""

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class RoleCreate(RoleBase):
    """Schema for role creation."""

    permission_ids: list[UUID] = []


class RoleUpdate(BaseModel):
    """Schema for role updates."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    permission_ids: list[UUID] | None = None


class RoleResponse(RoleBase):
    """Schema for role responses."""

    id: UUID
    is_system: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleWithPermissions(RoleResponse):
    """Role response with permissions."""

    permissions: list[PermissionResponse] = []


class RoleListResponse(BaseModel):
    """Paginated role list response."""

    items: list[RoleResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AssignRoleRequest(BaseModel):
    """Schema for assigning roles to users."""

    user_id: UUID
    role_ids: list[UUID]
    organization_id: UUID | None = None
    team_id: UUID | None = None


class CheckPermissionRequest(BaseModel):
    """Schema for checking permissions."""

    resource: str
    action: str
    organization_id: UUID | None = None
    team_id: UUID | None = None
