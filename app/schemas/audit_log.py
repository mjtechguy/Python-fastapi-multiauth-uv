"""Audit log schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AuditStatus = Literal["success", "failure", "error"]


class AuditLogCreate(BaseModel):
    """Schema for creating an audit log entry."""

    action: str = Field(min_length=1, max_length=100, description="Action performed")
    status: AuditStatus = Field(description="Result of the action")
    resource_type: str | None = Field(None, max_length=100, description="Type of resource affected")
    resource_id: str | None = Field(None, max_length=255, description="ID of affected resource")
    extra_data: dict | None = Field(None, description="Additional context data")


class AuditLogResponse(BaseModel):
    """Schema for audit log responses."""

    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    user_agent: str | None
    extra_data: dict
    status: AuditStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogDetailResponse(AuditLogResponse):
    """Detailed audit log response with user information."""

    user_email: str | None = None
    user_name: str | None = None


class AuditLogListResponse(BaseModel):
    """Paginated audit log list response."""

    items: list[AuditLogResponse]
    total: int
    page: int = 1
    page_size: int = 100
    pages: int = 1


class AuditLogSearchRequest(BaseModel):
    """Schema for searching audit logs."""

    search_term: str = Field(min_length=1, description="Search term for action or resource type")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(100, ge=1, le=500, description="Items per page")


class AuditLogFilterRequest(BaseModel):
    """Schema for filtering audit logs."""

    user_id: UUID | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    status: AuditStatus | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(100, ge=1, le=500)


class AuditLogStatistics(BaseModel):
    """Schema for audit log statistics."""

    total: int
    by_status: dict[str, int]
    unique_users: int


class AuditLogStatsRequest(BaseModel):
    """Schema for statistics request."""

    start_date: datetime | None = Field(None, description="Start date for statistics")
    end_date: datetime | None = Field(None, description="End date for statistics")


class LoginHistoryResponse(BaseModel):
    """Schema for login history response."""

    items: list[AuditLogResponse]
    total: int
