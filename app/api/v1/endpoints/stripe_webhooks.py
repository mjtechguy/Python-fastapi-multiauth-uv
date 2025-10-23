"""Stripe webhook handler endpoint."""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.services.billing_service import BillingService
from app.services.stripe_service import StripeService
from app.core.config import settings
from app.core.logging_config import logger

import stripe
from uuid import UUID

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """
    Handle Stripe webhook events.

    This endpoint receives webhook events from Stripe and processes them.
    Events are verified using the webhook signature to ensure authenticity.
    """
    # Get raw body and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    # Verify webhook signature
    try:
        event = StripeService.construct_webhook_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    logger.info(
        f"Received Stripe webhook event",
        extra={"event_type": event.type, "event_id": event.id},
    )

    # Check for duplicate event (idempotency)
    existing_event = await db.execute(
        select(BillingService).where(
            BillingService.stripe_event_id == event.id
        )
    )
    if existing_event.scalar_one_or_none():
        logger.info(
            f"Duplicate webhook event, skipping",
            extra={"event_id": event.id},
        )
        return {"status": "duplicate_event"}

    # Route to appropriate handler
    try:
        if event.type.startswith("customer.subscription"):
            await handle_subscription_event(db, event)
        elif event.type.startswith("invoice"):
            await handle_invoice_event(db, event)
        elif event.type.startswith("payment_method"):
            await handle_payment_method_event(db, event)
        else:
            logger.info(
                f"Unhandled webhook event type",
                extra={"event_type": event.type},
            )

        await db.commit()

        return {"status": "success"}

    except Exception as e:
        await db.rollback()
        logger.error(
            f"Error processing webhook event",
            extra={"event_type": event.type, "event_id": event.id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}",
        )


# ============================================================================
# Subscription Event Handlers
# ============================================================================


async def handle_subscription_event(db: AsyncSession, event: stripe.Event) -> None:
    """Handle subscription-related webhook events."""
    subscription_data = event.data.object

    # Get organization from metadata
    organization_id = subscription_data.metadata.get("organization_id")
    if not organization_id:
        logger.warning(
            "No organization_id in subscription metadata",
            extra={"subscription_id": subscription_data.id},
        )
        return

    try:
        org_uuid = UUID(organization_id)
    except ValueError:
        logger.error(
            "Invalid organization_id in metadata",
            extra={"organization_id": organization_id},
        )
        return

    # Get organization
    result = await db.execute(
        select(Organization).where(Organization.id == org_uuid)
    )
    org = result.scalar_one_or_none()

    if not org:
        logger.error(
            "Organization not found",
            extra={"organization_id": organization_id},
        )
        return

    if event.type == "customer.subscription.created":
        await handle_subscription_created(db, org, subscription_data, event.id)

    elif event.type == "customer.subscription.updated":
        await handle_subscription_updated(db, org, subscription_data, event.id)

    elif event.type == "customer.subscription.deleted":
        await handle_subscription_deleted(db, org, subscription_data, event.id)

    elif event.type == "customer.subscription.trial_will_end":
        await handle_trial_will_end(db, org, subscription_data, event.id)


async def handle_subscription_created(
    db: AsyncSession,
    org: Organization,
    subscription_data: stripe.Subscription,
    event_id: str,
) -> None:
    """Handle subscription.created event."""
    # Get plan from metadata
    plan_id = subscription_data.metadata.get("plan_id")
    if not plan_id:
        logger.warning("No plan_id in subscription metadata")
        return

    try:
        plan_uuid = UUID(plan_id)
    except ValueError:
        logger.error("Invalid plan_id in metadata", extra={"plan_id": plan_id})
        return

    # Create or update subscription
    subscription = await BillingService.get_organization_subscription(db, org.id)

    if subscription:
        # Update existing subscription
        await BillingService.update_subscription_from_stripe(
            db, subscription, subscription_data
        )
        subscription.plan_id = plan_uuid
    else:
        # Create new subscription
        subscription = await BillingService.create_paid_subscription(
            db, org.id, plan_uuid, subscription_data
        )

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org.id,
        event_type="subscription.created",
        event_data={"subscription_id": subscription_data.id},
        stripe_event_id=event_id,
        subscription_id=subscription.id,
    )

    logger.info(
        "Processed subscription.created",
        extra={"organization_id": str(org.id), "subscription_id": subscription_data.id},
    )


async def handle_subscription_updated(
    db: AsyncSession,
    org: Organization,
    subscription_data: stripe.Subscription,
    event_id: str,
) -> None:
    """Handle subscription.updated event."""
    subscription = await BillingService.get_organization_subscription(db, org.id)

    if not subscription:
        logger.warning(
            "Subscription not found for update",
            extra={"organization_id": str(org.id)},
        )
        return

    # Update subscription
    await BillingService.update_subscription_from_stripe(
        db, subscription, subscription_data
    )

    # Check if plan changed
    if subscription_data.metadata.get("plan_id"):
        try:
            new_plan_id = UUID(subscription_data.metadata["plan_id"])
            if subscription.plan_id != new_plan_id:
                # Plan changed, update quotas
                plan = await BillingService.get_plan_by_id(db, new_plan_id)
                if plan:
                    subscription.plan_id = new_plan_id
                    await BillingService.update_quotas_from_plan(db, org.id, plan)
        except (ValueError, KeyError):
            pass

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org.id,
        event_type="subscription.updated",
        event_data={
            "subscription_id": subscription_data.id,
            "status": subscription_data.status,
        },
        stripe_event_id=event_id,
        subscription_id=subscription.id,
    )

    logger.info(
        "Processed subscription.updated",
        extra={
            "organization_id": str(org.id),
            "subscription_id": subscription_data.id,
            "status": subscription_data.status,
        },
    )


async def handle_subscription_deleted(
    db: AsyncSession,
    org: Organization,
    subscription_data: stripe.Subscription,
    event_id: str,
) -> None:
    """Handle subscription.deleted event (cancellation)."""
    subscription = await BillingService.get_organization_subscription(db, org.id)

    if not subscription:
        logger.warning(
            "Subscription not found for deletion",
            extra={"organization_id": str(org.id)},
        )
        return

    # Update subscription status
    await BillingService.update_subscription_from_stripe(
        db, subscription, subscription_data
    )

    # Downgrade to free plan
    free_plan = await BillingService.get_plan_by_name(db, "free")
    if free_plan:
        subscription.plan_id = free_plan.id
        await BillingService.update_quotas_from_plan(db, org.id, free_plan)

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org.id,
        event_type="subscription.deleted",
        event_data={"subscription_id": subscription_data.id},
        stripe_event_id=event_id,
        subscription_id=subscription.id,
    )

    logger.info(
        "Processed subscription.deleted - downgraded to free",
        extra={"organization_id": str(org.id), "subscription_id": subscription_data.id},
    )


async def handle_trial_will_end(
    db: AsyncSession,
    org: Organization,
    subscription_data: stripe.Subscription,
    event_id: str,
) -> None:
    """Handle subscription.trial_will_end event (3 days before trial ends)."""
    subscription = await BillingService.get_organization_subscription(db, org.id)

    if not subscription:
        return

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org.id,
        event_type="subscription.trial_will_end",
        event_data={
            "subscription_id": subscription_data.id,
            "trial_end": subscription_data.trial_end,
        },
        stripe_event_id=event_id,
        subscription_id=subscription.id,
    )

    # TODO: Send email notification to user
    # This would be a good place to trigger a Celery task to send an email

    logger.info(
        "Processed subscription.trial_will_end",
        extra={"organization_id": str(org.id)},
    )


# ============================================================================
# Invoice Event Handlers
# ============================================================================


async def handle_invoice_event(db: AsyncSession, event: stripe.Event) -> None:
    """Handle invoice-related webhook events."""
    invoice_data = event.data.object

    # Get customer
    customer_id = invoice_data.customer
    if not customer_id:
        logger.warning("No customer in invoice data")
        return

    # Find organization by customer ID
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(
            "No subscription found for customer",
            extra={"customer_id": customer_id},
        )
        return

    org_id = subscription.organization_id

    if event.type == "invoice.payment_succeeded":
        await handle_invoice_payment_succeeded(db, org_id, invoice_data, event.id)

    elif event.type == "invoice.payment_failed":
        await handle_invoice_payment_failed(db, org_id, invoice_data, event.id)

    elif event.type in ["invoice.created", "invoice.finalized", "invoice.updated"]:
        # Just save/update the invoice
        await BillingService.save_invoice(db, org_id, invoice_data)


async def handle_invoice_payment_succeeded(
    db: AsyncSession,
    org_id: UUID,
    invoice_data: stripe.Invoice,
    event_id: str,
) -> None:
    """Handle invoice.payment_succeeded event."""
    # Save invoice
    invoice = await BillingService.save_invoice(db, org_id, invoice_data)

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org_id,
        event_type="invoice.payment_succeeded",
        event_data={
            "invoice_id": invoice_data.id,
            "amount_paid": invoice_data.amount_paid,
        },
        stripe_event_id=event_id,
    )

    # TODO: Send receipt email if enabled
    if settings.BILLING_SEND_RECEIPTS:
        # Trigger Celery task to send email
        pass

    logger.info(
        "Processed invoice.payment_succeeded",
        extra={"organization_id": str(org_id), "invoice_id": invoice_data.id},
    )


async def handle_invoice_payment_failed(
    db: AsyncSession,
    org_id: UUID,
    invoice_data: stripe.Invoice,
    event_id: str,
) -> None:
    """Handle invoice.payment_failed event."""
    # Save invoice
    invoice = await BillingService.save_invoice(db, org_id, invoice_data)

    # Update subscription status
    subscription = await BillingService.get_organization_subscription(db, org_id)
    if subscription and subscription.status != "past_due":
        subscription.status = "past_due"

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org_id,
        event_type="invoice.payment_failed",
        event_data={
            "invoice_id": invoice_data.id,
            "amount_due": invoice_data.amount_due,
        },
        stripe_event_id=event_id,
    )

    # TODO: Send payment failed email
    # Trigger Celery task to send email notification

    logger.warning(
        "Processed invoice.payment_failed",
        extra={"organization_id": str(org_id), "invoice_id": invoice_data.id},
    )


# ============================================================================
# Payment Method Event Handlers
# ============================================================================


async def handle_payment_method_event(db: AsyncSession, event: stripe.Event) -> None:
    """Handle payment method-related webhook events."""
    pm_data = event.data.object

    # Get customer
    customer_id = pm_data.customer
    if not customer_id:
        return

    # Find organization
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        return

    if event.type == "payment_method.attached":
        await handle_payment_method_attached(db, subscription.organization_id, pm_data, event.id)

    elif event.type == "payment_method.detached":
        await handle_payment_method_detached(db, subscription.organization_id, pm_data, event.id)


async def handle_payment_method_attached(
    db: AsyncSession,
    org_id: UUID,
    pm_data: stripe.PaymentMethod,
    event_id: str,
) -> None:
    """Handle payment_method.attached event."""
    # Check if already exists
    from app.models.payment_method import PaymentMethod

    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.stripe_payment_method_id == pm_data.id
        )
    )
    existing = result.scalar_one_or_none()

    if not existing:
        # Save payment method
        await BillingService.save_payment_method(db, org_id, pm_data)

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org_id,
        event_type="payment_method.attached",
        event_data={"payment_method_id": pm_data.id, "type": pm_data.type},
        stripe_event_id=event_id,
    )

    logger.info(
        "Processed payment_method.attached",
        extra={"organization_id": str(org_id), "payment_method_id": pm_data.id},
    )


async def handle_payment_method_detached(
    db: AsyncSession,
    org_id: UUID,
    pm_data: stripe.PaymentMethod,
    event_id: str,
) -> None:
    """Handle payment_method.detached event."""
    from app.models.payment_method import PaymentMethod

    # Remove from database
    result = await db.execute(
        select(PaymentMethod).where(
            PaymentMethod.stripe_payment_method_id == pm_data.id,
            PaymentMethod.organization_id == org_id,
        )
    )
    payment_method = result.scalar_one_or_none()

    if payment_method:
        await db.delete(payment_method)

    # Log event
    await BillingService.log_billing_event(
        db=db,
        organization_id=org_id,
        event_type="payment_method.detached",
        event_data={"payment_method_id": pm_data.id},
        stripe_event_id=event_id,
    )

    logger.info(
        "Processed payment_method.detached",
        extra={"organization_id": str(org_id), "payment_method_id": pm_data.id},
    )
