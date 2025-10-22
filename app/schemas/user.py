"""User schemas for API validation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    username: str | None = None
    full_name: str | None = None


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        from app.core.security import validate_password_strength

        is_valid, error_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class UserUpdate(BaseModel):
    """Schema for user updates."""

    username: str | None = None
    full_name: str | None = None
    email: EmailStr | None = None


class UserPasswordUpdate(BaseModel):
    """Schema for password updates."""

    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        from app.core.security import validate_password_strength

        is_valid, error_msg = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_msg)
        return v


class UserResponse(UserBase):
    """Schema for user responses."""

    id: UUID
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserWithRoles(UserResponse):
    """User response with role information."""

    roles: list["RoleResponse"] = []


class UserListResponse(BaseModel):
    """Paginated user list response."""

    items: list[UserResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Forward references
from app.schemas.role import RoleResponse

UserWithRoles.model_rebuild()
