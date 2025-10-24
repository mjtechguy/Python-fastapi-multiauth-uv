"""Webhook service for event notifications."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import Webhook, WebhookDelivery


class WebhookService:
    """Service for managing webhooks."""

    # Available webhook events
    AVAILABLE_EVENTS = {
        "user.created": "Triggered when a new user is created",
        "user.updated": "Triggered when a user is updated",
        "user.deleted": "Triggered when a user is deleted",
        "file.uploaded": "Triggered when a file is uploaded",
        "file.deleted": "Triggered when a file is deleted",
        "organization.created": "Triggered when an organization is created",
        "organization.updated": "Triggered when an organization is updated",
        "organization.deleted": "Triggered when an organization is deleted",
        "api_key.created": "Triggered when an API key is created",
        "api_key.revoked": "Triggered when an API key is revoked",
        "session.created": "Triggered when a user session is created",
        "session.expired": "Triggered when a user session expires",
        "test.event": "Test event for webhook verification",
    }

    @staticmethod
    def generate_secret() -> str:
        """Generate a secure webhook secret."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload."""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    async def create_webhook(
        db: AsyncSession,
        organization_id: uuid.UUID,
        url: str,
        events: list[str],
        description: str | None = None,
    ) -> Webhook:
        """Create a new webhook."""
        # Validate events
        invalid_events = [e for e in events if e not in WebhookService.AVAILABLE_EVENTS]
        if invalid_events:
            raise ValueError(f"Invalid events: {', '.join(invalid_events)}")

        webhook = Webhook(
            organization_id=organization_id,
            url=url,
            secret=WebhookService.generate_secret(),
            events=events,
            description=description,
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        return webhook

    @staticmethod
    async def update_webhook(
        db: AsyncSession,
        webhook_id: uuid.UUID,
        **updates: Any
    ) -> Webhook:
        """Update a webhook."""
        result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
        webhook = result.scalar_one_or_none()
        if not webhook:
            raise ValueError("Webhook not found")

        # Validate events if provided
        if updates.get("events"):
            invalid_events = [e for e in updates["events"] if e not in WebhookService.AVAILABLE_EVENTS]
            if invalid_events:
                raise ValueError(f"Invalid events: {', '.join(invalid_events)}")

        for key, value in updates.items():
            if value is not None and hasattr(webhook, key):
                setattr(webhook, key, value)

        await db.commit()
        await db.refresh(webhook)
        return webhook

    @staticmethod
    async def delete_webhook(db: AsyncSession, webhook_id: uuid.UUID) -> None:
        """Delete a webhook."""
        result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
        webhook = result.scalar_one_or_none()
        if webhook:
            await db.delete(webhook)
            await db.commit()

    @staticmethod
    async def get_webhook(db: AsyncSession, webhook_id: uuid.UUID) -> Webhook | None:
        """Get a webhook by ID."""
        result = await db.execute(select(Webhook).where(Webhook.id == webhook_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_webhooks(
        db: AsyncSession,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Webhook], int]:
        """List webhooks for an organization."""
        query = select(Webhook).where(Webhook.organization_id == organization_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(Webhook.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        webhooks = list(result.scalars().all())

        return webhooks, total

    @staticmethod
    async def create_delivery(
        db: AsyncSession,
        webhook_id: uuid.UUID,
        event_type: str,
        event_data: dict[str, Any],
    ) -> WebhookDelivery:
        """Create a webhook delivery record."""
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_type=event_type,
            event_data=event_data,
            status="pending",
        )
        db.add(delivery)
        await db.commit()
        await db.refresh(delivery)
        return delivery

    @staticmethod
    async def deliver_webhook(
        db: AsyncSession,
        delivery: WebhookDelivery,
    ) -> bool:
        """Deliver a webhook (synchronous delivery for testing/immediate delivery)."""
        # Get webhook
        result = await db.execute(select(Webhook).where(Webhook.id == delivery.webhook_id))
        webhook = result.scalar_one_or_none()
        if not webhook or not webhook.is_active:
            delivery.status = "failed"
            delivery.error_message = "Webhook not found or inactive"
            await db.commit()
            return False

        # Prepare payload
        import json
        payload = json.dumps({
            "event_type": delivery.event_type,
            "event_data": delivery.event_data,
            "delivery_id": str(delivery.id),
            "webhook_id": str(webhook.id),
            "timestamp": datetime.now(UTC).isoformat(),
        })

        # Generate signature
        signature = WebhookService.generate_signature(payload, webhook.secret)

        # Send request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook.url,
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                        "X-Webhook-Event": delivery.event_type,
                        "X-Webhook-Delivery": str(delivery.id),
                    }
                )

                delivery.status_code = response.status_code
                delivery.response_body = response.text[:1000]  # Limit response body size
                delivery.attempt_count += 1
                delivery.delivered_at = datetime.now(UTC)

                if 200 <= response.status_code < 300:
                    delivery.status = "success"
                    webhook.successful_deliveries += 1
                    webhook.last_success_at = datetime.now(UTC)
                else:
                    delivery.status = "failed"
                    delivery.error_message = f"HTTP {response.status_code}"
                    webhook.failed_deliveries += 1
                    webhook.last_failure_at = datetime.now(UTC)

                    # Schedule retry
                    if delivery.attempt_count < delivery.max_attempts:
                        delivery.status = "retrying"
                        # Exponential backoff: 5min, 30min, 2h
                        retry_delays = [300, 1800, 7200]
                        delay = retry_delays[min(delivery.attempt_count - 1, len(retry_delays) - 1)]
                        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)

        except Exception as e:
            delivery.status = "failed"
            delivery.error_message = str(e)[:1000]
            delivery.attempt_count += 1
            delivery.delivered_at = datetime.now(UTC)
            webhook.failed_deliveries += 1
            webhook.last_failure_at = datetime.now(UTC)

            # Schedule retry
            if delivery.attempt_count < delivery.max_attempts:
                delivery.status = "retrying"
                retry_delays = [300, 1800, 7200]
                delay = retry_delays[min(delivery.attempt_count - 1, len(retry_delays) - 1)]
                delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay)

        webhook.total_deliveries += 1
        webhook.last_delivery_at = datetime.now(UTC)
        await db.commit()

        return delivery.status == "success"

    @staticmethod
    async def trigger_event(
        db: AsyncSession,
        organization_id: uuid.UUID,
        event_type: str,
        event_data: dict[str, Any],
    ) -> list[WebhookDelivery]:
        """Trigger an event and create deliveries for all matching webhooks."""
        # Find all active webhooks subscribed to this event
        result = await db.execute(
            select(Webhook).where(
                Webhook.organization_id == organization_id,
                Webhook.is_active,
            )
        )
        webhooks = list(result.scalars().all())

        deliveries = []
        for webhook in webhooks:
            if event_type in webhook.events:
                delivery = await WebhookService.create_delivery(
                    db, webhook.id, event_type, event_data
                )
                deliveries.append(delivery)

        return deliveries

    @staticmethod
    async def get_deliveries(
        db: AsyncSession,
        webhook_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[WebhookDelivery], int]:
        """Get deliveries for a webhook."""
        query = select(WebhookDelivery).where(WebhookDelivery.webhook_id == webhook_id)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        # Get paginated results
        query = query.order_by(WebhookDelivery.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        deliveries = list(result.scalars().all())

        return deliveries, total
