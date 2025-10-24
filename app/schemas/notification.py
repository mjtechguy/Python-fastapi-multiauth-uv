"""Notification schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

NotificationType = Literal["info", "success", "warning", "error"]


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""

    type: NotificationType = Field(description="Notification type")
    title: str = Field(min_length=1, max_length=255, description="Notification title")
    message: str = Field(min_length=1, description="Notification message")
    action_url: str | None = Field(None, max_length=500, description="Optional action URL")
    action_label: str | None = Field(None, max_length=100, description="Optional action button label")
    extra_data: dict | None = Field(None, description="Optional additional data")


class NotificationResponse(BaseModel):
    """Schema for notification responses."""

    id: UUID
    user_id: UUID
    type: NotificationType
    title: str
    message: str
    action_url: str | None = None
    action_label: str | None = None
    is_read: bool
    read_at: datetime | None = None
    extra_data: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Paginated notification list response."""

    items: list[NotificationResponse]
    total: int
    unread_count: int
    page: int = 1
    page_size: int = 50
    pages: int = 1


class NotificationMarkReadRequest(BaseModel):
    """Schema for marking notification as read."""

    notification_id: UUID


class NotificationMarkAllReadResponse(BaseModel):
    """Schema for mark all as read response."""

    message: str
    count: int


class NotificationDeleteResponse(BaseModel):
    """Schema for notification deletion response."""

    message: str
    count: int | None = None


class NotificationUnreadCountResponse(BaseModel):
    """Schema for unread count response."""

    unread_count: int


class NotificationBroadcastRequest(BaseModel):
    """Schema for broadcasting notification to multiple users."""

    user_ids: list[UUID] = Field(min_length=1, description="List of user IDs to notify")
    type: NotificationType = Field(description="Notification type")
    title: str = Field(min_length=1, max_length=255, description="Notification title")
    message: str = Field(min_length=1, description="Notification message")
    action_url: str | None = Field(None, max_length=500, description="Optional action URL")
    action_label: str | None = Field(None, max_length=100, description="Optional action button label")
    extra_data: dict | None = Field(None, description="Optional additional data")


class NotificationBroadcastResponse(BaseModel):
    """Schema for broadcast response."""

    message: str
    notifications_created: int
