"""Webhook schemas for API validation."""

import uuid
from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl


class WebhookCreate(BaseModel):
    """Schema for creating a webhook."""

    url: str = Field(..., description="Webhook URL to send events to")
    description: str | None = Field(None, description="Description of the webhook")
    events: list[str] = Field(
        ...,
        min_length=1,
        description="List of events to subscribe to (e.g., user.created, file.uploaded)"
    )


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook."""

    url: str | None = Field(None, description="Webhook URL to send events to")
    description: str | None = Field(None, description="Description of the webhook")
    events: list[str] | None = Field(None, description="List of events to subscribe to")
    is_active: bool | None = Field(None, description="Whether the webhook is active")


class WebhookResponse(BaseModel):
    """Schema for webhook response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    url: str
    secret: str = Field(..., description="Secret for HMAC signature verification")
    description: str | None
    events: list[str]
    is_active: bool
    total_deliveries: int
    successful_deliveries: int
    failed_deliveries: int
    last_delivery_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WebhookListResponse(BaseModel):
    """Schema for paginated webhook list."""

    webhooks: list[WebhookResponse]
    total: int
    page: int
    page_size: int


class WebhookDeliveryResponse(BaseModel):
    """Schema for webhook delivery record."""

    id: uuid.UUID
    webhook_id: uuid.UUID
    event_type: str
    event_data: dict
    status: str
    status_code: int | None
    response_body: str | None
    error_message: str | None
    attempt_count: int
    max_attempts: int
    next_retry_at: datetime | None
    created_at: datetime
    delivered_at: datetime | None

    class Config:
        from_attributes = True


class WebhookDeliveryListResponse(BaseModel):
    """Schema for paginated webhook delivery list."""

    deliveries: list[WebhookDeliveryResponse]
    total: int
    page: int
    page_size: int


class WebhookTestRequest(BaseModel):
    """Schema for testing a webhook."""

    event_type: str = Field("test.event", description="Event type for testing")
    event_data: dict = Field(default_factory=dict, description="Custom event data for testing")


class WebhookTestResponse(BaseModel):
    """Schema for webhook test response."""

    message: str
    delivery: WebhookDeliveryResponse


class AvailableEventsResponse(BaseModel):
    """Schema for listing available webhook events."""

    events: list[str] = Field(..., description="List of available event types")
    descriptions: dict[str, str] = Field(
        ..., description="Descriptions of each event type"
    )
