"""Celery tasks for webhook delivery."""

import uuid
from typing import Any

from app.tasks.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.webhook import WebhookService
from app.models.webhook import WebhookDelivery
from sqlalchemy import select


@celery_app.task(
    name="deliver_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def deliver_webhook_task(self, delivery_id: str) -> dict[str, Any]:
    """
    Deliver a webhook asynchronously.

    Args:
        delivery_id: UUID of the webhook delivery record

    Returns:
        Dictionary with delivery status
    """
    import asyncio

    async def _deliver():
        async with AsyncSessionLocal() as db:
            # Get delivery
            result = await db.execute(
                select(WebhookDelivery).where(WebhookDelivery.id == uuid.UUID(delivery_id))
            )
            delivery = result.scalar_one_or_none()

            if not delivery:
                return {"status": "error", "message": "Delivery not found"}

            # Deliver webhook
            success = await WebhookService.deliver_webhook(db, delivery)

            return {
                "status": "success" if success else "failed",
                "delivery_id": delivery_id,
                "attempt_count": delivery.attempt_count,
                "status_code": delivery.status_code,
            }

    try:
        return asyncio.run(_deliver())
    except Exception as exc:
        # Retry on failure
        raise self.retry(exc=exc)


@celery_app.task(name="trigger_webhook_event")
def trigger_webhook_event_task(
    organization_id: str,
    event_type: str,
    event_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Trigger a webhook event and create deliveries.

    Args:
        organization_id: UUID of the organization
        event_type: Type of event (e.g., user.created)
        event_data: Event data payload

    Returns:
        Dictionary with created delivery IDs
    """
    import asyncio

    async def _trigger():
        async with AsyncSessionLocal() as db:
            deliveries = await WebhookService.trigger_event(
                db,
                uuid.UUID(organization_id),
                event_type,
                event_data,
            )

            # Schedule delivery tasks
            for delivery in deliveries:
                deliver_webhook_task.delay(str(delivery.id))

            return {
                "status": "success",
                "deliveries_created": len(deliveries),
                "delivery_ids": [str(d.id) for d in deliveries],
            }

    return asyncio.run(_trigger())


@celery_app.task(name="retry_failed_webhooks")
def retry_failed_webhooks_task() -> dict[str, Any]:
    """
    Periodic task to retry failed webhook deliveries.
    Should be scheduled to run every 5 minutes.

    Returns:
        Dictionary with retry statistics
    """
    import asyncio
    from datetime import datetime

    async def _retry():
        async with AsyncSessionLocal() as db:
            # Find deliveries ready for retry
            result = await db.execute(
                select(WebhookDelivery).where(
                    WebhookDelivery.status == "retrying",
                    WebhookDelivery.next_retry_at <= datetime.utcnow(),
                )
            )
            deliveries = list(result.scalars().all())

            # Schedule retry tasks
            for delivery in deliveries:
                deliver_webhook_task.delay(str(delivery.id))

            return {
                "status": "success",
                "retries_scheduled": len(deliveries),
            }

    return asyncio.run(_retry())
