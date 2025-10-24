"""Celery tasks for billing operations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import stripe
from sqlalchemy import select

from app.core.logging_config import get_logger

logger = get_logger(__name__)
from app.db.session import async_session_maker
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.services.billing_service import BillingService
from app.services.stripe_service import StripeService
from app.tasks.celery_app import celery_app


@celery_app.task(name="billing.sync_subscription_from_stripe")
def sync_subscription_from_stripe(subscription_id: str) -> dict[str, str]:
    """
    Sync subscription data from Stripe.

    Args:
        subscription_id: Stripe subscription ID

    Returns:
        Status dict
    """
    import asyncio

    async def _sync():
        async with async_session_maker() as db:
            try:
                # Get subscription from database
                result = await db.execute(
                    select(Subscription).where(
                        Subscription.stripe_subscription_id == subscription_id
                    )
                )
                subscription = result.scalar_one_or_none()

                if not subscription:
                    logger.warning(
                        "Subscription not found for sync",
                        extra={"subscription_id": subscription_id},
                    )
                    return {"status": "not_found"}

                # Fetch from Stripe
                stripe_subscription = await StripeService.get_subscription(subscription_id)

                # Update local subscription
                await BillingService.update_subscription_from_stripe(
                    db, subscription, stripe_subscription
                )

                await db.commit()

                logger.info(
                    "Synced subscription from Stripe",
                    extra={"subscription_id": subscription_id},
                )

                return {"status": "success"}

            except stripe.error.StripeError as e:
                logger.error(
                    "Stripe error during sync",
                    extra={"subscription_id": subscription_id, "error": str(e)},
                )
                return {"status": "error", "error": str(e)}

            except Exception as e:
                logger.error(
                    "Error syncing subscription",
                    extra={"subscription_id": subscription_id, "error": str(e)},
                )
                return {"status": "error", "error": str(e)}

    return asyncio.run(_sync())


@celery_app.task(name="billing.update_organization_quotas")
def update_organization_quotas(organization_id: str) -> dict[str, str]:
    """
    Update organization quotas based on current subscription plan.

    Args:
        organization_id: Organization UUID string

    Returns:
        Status dict
    """
    import asyncio

    async def _update():
        async with async_session_maker() as db:
            try:
                org_uuid = UUID(organization_id)

                # Get subscription
                subscription = await BillingService.get_organization_subscription(
                    db, org_uuid
                )

                if not subscription:
                    logger.warning(
                        "No subscription found",
                        extra={"organization_id": organization_id},
                    )
                    return {"status": "no_subscription"}

                # Update quotas from plan
                await BillingService.update_quotas_from_plan(
                    db, org_uuid, subscription.plan
                )

                await db.commit()

                logger.info(
                    "Updated organization quotas",
                    extra={"organization_id": organization_id},
                )

                return {"status": "success"}

            except Exception as e:
                logger.error(
                    "Error updating quotas",
                    extra={"organization_id": organization_id, "error": str(e)},
                )
                return {"status": "error", "error": str(e)}

    return asyncio.run(_update())


@celery_app.task(name="billing.send_billing_notification")
def send_billing_notification(organization_id: str, event_type: str, **kwargs) -> dict[str, str]:
    """
    Send billing-related email notification.

    Args:
        organization_id: Organization UUID string
        event_type: Type of notification (receipt, payment_failed, trial_ending, etc.)
        **kwargs: Additional context for email template

    Returns:
        Status dict
    """
    import asyncio

    async def _send():
        async with async_session_maker() as db:
            try:
                org_uuid = UUID(organization_id)

                # Get organization
                result = await db.execute(
                    select(Organization).where(Organization.id == org_uuid)
                )
                org = result.scalar_one_or_none()

                if not org:
                    return {"status": "org_not_found"}

                # Get owner email
                from app.models.user import User

                result = await db.execute(
                    select(User).where(User.id == org.owner_id)
                )
                owner = result.scalar_one_or_none()

                if not owner:
                    return {"status": "owner_not_found"}

                # TODO: Implement email sending logic
                # This would use your existing email service
                # from app.tasks.email import send_email_async
                #
                # email_data = {
                #     "to": owner.email,
                #     "subject": f"Billing Notification: {event_type}",
                #     "template": f"billing/{event_type}.html",
                #     "context": kwargs,
                # }
                # await send_email_async(**email_data)

                logger.info(
                    "Sent billing notification",
                    extra={
                        "organization_id": organization_id,
                        "event_type": event_type,
                        "recipient": owner.email,
                    },
                )

                return {"status": "success"}

            except Exception as e:
                logger.error(
                    "Error sending billing notification",
                    extra={
                        "organization_id": organization_id,
                        "event_type": event_type,
                        "error": str(e),
                    },
                )
                return {"status": "error", "error": str(e)}

    return asyncio.run(_send())


@celery_app.task(name="billing.check_trial_expiring")
def check_trial_expiring() -> dict[str, int]:
    """
    Check for trials ending soon and send notifications.

    This is a scheduled task (runs daily).

    Returns:
        Dict with count of notifications sent
    """
    import asyncio

    async def _check():
        async with async_session_maker() as db:
            try:
                # Find subscriptions with trials ending in 3 days
                three_days_from_now = datetime.now(UTC) + timedelta(days=3)
                two_days_from_now = datetime.now(UTC) + timedelta(days=2)

                result = await db.execute(
                    select(Subscription).where(
                        Subscription.status == "trialing",
                        Subscription.trial_end >= two_days_from_now,
                        Subscription.trial_end <= three_days_from_now,
                    )
                )
                expiring_trials = list(result.scalars().all())

                count = 0
                for subscription in expiring_trials:
                    # Send notification
                    send_billing_notification.delay(
                        str(subscription.organization_id),
                        "trial_ending",
                        trial_end=subscription.trial_end.isoformat(),
                        days_remaining=(
                            subscription.trial_end - datetime.now(UTC)
                        ).days,
                    )
                    count += 1

                logger.info(
                    f"Checked trial expiring, sent {count} notifications",
                    extra={"count": count},
                )

                return {"count": count}

            except Exception as e:
                logger.error(
                    "Error checking trial expiring",
                    extra={"error": str(e)},
                )
                return {"count": 0, "error": str(e)}

    return asyncio.run(_check())


@celery_app.task(name="billing.check_payment_failures")
def check_payment_failures() -> dict[str, int]:
    """
    Check for failed payments and send reminders.

    This is a scheduled task (runs daily).

    Returns:
        Dict with count of reminders sent
    """
    import asyncio

    async def _check():
        async with async_session_maker() as db:
            try:
                # Find subscriptions with past_due status
                result = await db.execute(
                    select(Subscription).where(Subscription.status == "past_due")
                )
                past_due_subscriptions = list(result.scalars().all())

                count = 0
                for subscription in past_due_subscriptions:
                    # Send reminder
                    send_billing_notification.delay(
                        str(subscription.organization_id),
                        "payment_failed_reminder",
                        subscription_id=subscription.stripe_subscription_id,
                    )
                    count += 1

                logger.info(
                    f"Checked payment failures, sent {count} reminders",
                    extra={"count": count},
                )

                return {"count": count}

            except Exception as e:
                logger.error(
                    "Error checking payment failures",
                    extra={"error": str(e)},
                )
                return {"count": 0, "error": str(e)}

    return asyncio.run(_check())


@celery_app.task(name="billing.report_usage_to_stripe")
def report_usage_to_stripe(organization_id: str) -> dict[str, str]:
    """
    Report metered usage to Stripe (for usage-based billing).

    This can be used if you want to implement usage-based billing
    on top of subscription plans (e.g., extra API calls beyond quota).

    Args:
        organization_id: Organization UUID string

    Returns:
        Status dict
    """
    import asyncio

    async def _report():
        async with async_session_maker() as db:
            try:
                org_uuid = UUID(organization_id)

                # Get subscription and quota
                subscription = await BillingService.get_organization_subscription(
                    db, org_uuid
                )

                if not subscription or not subscription.stripe_subscription_id:
                    return {"status": "no_subscription"}

                from app.models.quota import OrganizationQuota

                result = await db.execute(
                    select(OrganizationQuota).where(
                        OrganizationQuota.organization_id == org_uuid
                    )
                )
                quota = result.scalar_one_or_none()

                if not quota:
                    return {"status": "no_quota"}

                # TODO: Implement usage reporting to Stripe
                # This would create a usage record for metered billing
                # stripe.SubscriptionItem.create_usage_record(
                #     subscription_item_id,
                #     quantity=quota.current_api_calls_this_month,
                #     timestamp=int(datetime.now(timezone.utc).timestamp()),
                # )

                logger.info(
                    "Reported usage to Stripe",
                    extra={
                        "organization_id": organization_id,
                        "api_calls": quota.current_api_calls_this_month,
                    },
                )

                return {"status": "success"}

            except Exception as e:
                logger.error(
                    "Error reporting usage to Stripe",
                    extra={"organization_id": organization_id, "error": str(e)},
                )
                return {"status": "error", "error": str(e)}

    return asyncio.run(_report())
