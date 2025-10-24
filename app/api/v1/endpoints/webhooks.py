"""Webhook management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.organization_helpers import get_user_organization_id
from app.db.session import get_db
from app.models.user import User
from app.schemas.webhook import (
    AvailableEventsResponse,
    WebhookCreate,
    WebhookCreatedResponse,
    WebhookDeliveryListResponse,
    WebhookListResponse,
    WebhookResponse,
    WebhookTestRequest,
    WebhookTestResponse,
    WebhookUpdate,
)
from app.services.webhook import WebhookService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/events", response_model=AvailableEventsResponse)
async def get_available_events() -> AvailableEventsResponse:
    """Get list of available webhook events."""
    return AvailableEventsResponse(
        events=list(WebhookService.AVAILABLE_EVENTS.keys()),
        descriptions=WebhookService.AVAILABLE_EVENTS,
    )


@router.post("", response_model=WebhookCreatedResponse, status_code=201)
async def create_webhook(
    request: WebhookCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookCreatedResponse:
    """Create a new webhook."""
    organization_id = get_user_organization_id(current_user)

    try:
        return await WebhookService.create_webhook(
            db,
            organization_id,
            request.url,
            request.events,
            request.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> WebhookListResponse:
    """List all webhooks for user's organization."""
    organization_id = get_user_organization_id(current_user)

    webhooks, total = await WebhookService.list_webhooks(
        db, organization_id, page, page_size
    )

    # Mask secrets in list response
    masked_webhooks = [WebhookResponse.from_webhook(w) for w in webhooks]

    return WebhookListResponse(
        webhooks=masked_webhooks,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    """Get a specific webhook."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Verify ownership
    organization_id = get_user_organization_id(current_user)
    if webhook.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return WebhookResponse.from_webhook(webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: uuid.UUID,
    request: WebhookUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookResponse:
    """Update a webhook."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Verify ownership
    organization_id = get_user_organization_id(current_user)
    if webhook.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        updated_webhook = await WebhookService.update_webhook(
            db,
            webhook_id,
            url=request.url,
            description=request.description,
            events=request.events,
            is_active=request.is_active,
        )
        return WebhookResponse.from_webhook(updated_webhook)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a webhook."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Verify ownership
    organization_id = get_user_organization_id(current_user)
    if webhook.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    await WebhookService.delete_webhook(db, webhook_id)


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: uuid.UUID,
    request: WebhookTestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookTestResponse:
    """Test a webhook by sending a test event."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Verify ownership
    organization_id = get_user_organization_id(current_user)
    if webhook.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Create delivery
    delivery = await WebhookService.create_delivery(
        db, webhook_id, request.event_type, request.event_data
    )

    # Deliver synchronously for immediate feedback
    await WebhookService.deliver_webhook(db, delivery)

    return WebhookTestResponse(
        message="Test webhook delivered",
        delivery=delivery,
    )


@router.get("/{webhook_id}/deliveries", response_model=WebhookDeliveryListResponse)
async def get_webhook_deliveries(
    webhook_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> WebhookDeliveryListResponse:
    """Get delivery history for a webhook."""
    webhook = await WebhookService.get_webhook(db, webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    # Verify ownership
    organization_id = get_user_organization_id(current_user)
    if webhook.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Access denied")

    deliveries, total = await WebhookService.get_deliveries(db, webhook_id, page, page_size)

    return WebhookDeliveryListResponse(
        deliveries=deliveries,
        total=total,
        page=page,
        page_size=page_size,
    )
