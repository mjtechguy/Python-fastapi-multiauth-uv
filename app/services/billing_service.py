"""Billing service for managing subscriptions and billing logic."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging_config import logger
from app.models.billing_event import BillingEvent
from app.models.invoice import Invoice
from app.models.payment_method import PaymentMethod
from app.models.quota import OrganizationQuota
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.services.stripe_service import StripeService


class BillingService:
    """Service for managing subscriptions and billing."""

    # ========================================================================
    # Subscription Plan Management
    # ========================================================================

    @staticmethod
    async def get_plan_by_id(db: AsyncSession, plan_id: UUID) -> SubscriptionPlan | None:
        """Get subscription plan by ID."""
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_plan_by_name(db: AsyncSession, name: str) -> SubscriptionPlan | None:
        """Get subscription plan by name."""
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == name)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_active_plans(db: AsyncSession) -> list[SubscriptionPlan]:
        """List all active subscription plans."""
        result = await db.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active)
            .order_by(SubscriptionPlan.tier_level)
        )
        return list(result.scalars().all())

    # ========================================================================
    # Subscription Management
    # ========================================================================

    @staticmethod
    async def get_organization_subscription(
        db: AsyncSession, organization_id: UUID
    ) -> Subscription | None:
        """Get organization's subscription with plan details."""
        result = await db.execute(
            select(Subscription)
            .where(Subscription.organization_id == organization_id)
            .options(selectinload(Subscription.plan))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_free_subscription(
        db: AsyncSession, organization_id: UUID, stripe_customer_id: str
    ) -> Subscription:
        """Create a free tier subscription for a new organization."""
        free_plan = await BillingService.get_plan_by_name(db, "free")
        if not free_plan:
            raise ValueError("Free plan not found")

        now = datetime.now(UTC)
        subscription = Subscription(
            organization_id=organization_id,
            plan_id=free_plan.id,
            stripe_customer_id=stripe_customer_id,
            status="active",
            current_period_start=now,
            current_period_end=now + timedelta(days=365),  # Year-long free period
        )

        db.add(subscription)
        await db.flush()

        # Update organization quotas to match free plan
        await BillingService.update_quotas_from_plan(db, organization_id, free_plan)

        logger.info(
            "Created free subscription",
            extra={"organization_id": str(organization_id), "plan": "free"},
        )

        return subscription

    @staticmethod
    async def create_paid_subscription(
        db: AsyncSession,
        organization_id: UUID,
        plan_id: UUID,
        stripe_subscription: stripe.Subscription,
    ) -> Subscription:
        """Create a paid subscription from Stripe subscription object."""
        plan = await BillingService.get_plan_by_id(db, plan_id)
        if not plan:
            raise ValueError(f"Plan not found: {plan_id}")

        # Parse dates from Stripe
        current_period_start = datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=UTC
        )
        current_period_end = datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=UTC
        )

        trial_start = None
        trial_end = None
        if stripe_subscription.trial_start:
            trial_start = datetime.fromtimestamp(
                stripe_subscription.trial_start, tz=UTC
            )
        if stripe_subscription.trial_end:
            trial_end = datetime.fromtimestamp(
                stripe_subscription.trial_end, tz=UTC
            )

        subscription = Subscription(
            organization_id=organization_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_subscription.customer,
            status=stripe_subscription.status,
            cancel_at_period_end=stripe_subscription.cancel_at_period_end,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            trial_start=trial_start,
            trial_end=trial_end,
            stripe_metadata=dict(stripe_subscription.metadata or {}),
        )

        db.add(subscription)
        await db.flush()

        # Update organization quotas
        await BillingService.update_quotas_from_plan(db, organization_id, plan)

        logger.info(
            "Created paid subscription",
            extra={
                "organization_id": str(organization_id),
                "plan": plan.name,
                "stripe_subscription_id": stripe_subscription.id,
            },
        )

        return subscription

    @staticmethod
    async def update_subscription_from_stripe(
        db: AsyncSession, subscription: Subscription, stripe_subscription: stripe.Subscription
    ) -> Subscription:
        """Update local subscription from Stripe subscription object."""
        subscription.status = stripe_subscription.status
        subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end

        if stripe_subscription.canceled_at:
            subscription.canceled_at = datetime.fromtimestamp(
                stripe_subscription.canceled_at, tz=UTC
            )

        subscription.current_period_start = datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=UTC
        )
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=UTC
        )

        if stripe_subscription.trial_start:
            subscription.trial_start = datetime.fromtimestamp(
                stripe_subscription.trial_start, tz=UTC
            )
        if stripe_subscription.trial_end:
            subscription.trial_end = datetime.fromtimestamp(
                stripe_subscription.trial_end, tz=UTC
            )

        subscription.stripe_metadata = dict(stripe_subscription.metadata or {})
        subscription.updated_at = datetime.now(UTC)

        logger.info(
            "Updated subscription from Stripe",
            extra={
                "subscription_id": str(subscription.id),
                "status": subscription.status,
            },
        )

        return subscription

    @staticmethod
    async def upgrade_subscription(
        db: AsyncSession,
        organization_id: UUID,
        new_plan_id: UUID,
        billing_cycle: str = "monthly",
        prorate: bool = True,
    ) -> Subscription:
        """
        Upgrade or downgrade organization subscription.

        Args:
            db: Database session
            organization_id: Organization UUID
            new_plan_id: New subscription plan UUID
            billing_cycle: "monthly" or "yearly"
            prorate: Whether to prorate the charges

        Returns:
            Updated Subscription object
        """
        subscription = await BillingService.get_organization_subscription(db, organization_id)
        if not subscription:
            raise ValueError("Subscription not found")

        new_plan = await BillingService.get_plan_by_id(db, new_plan_id)
        if not new_plan:
            raise ValueError("Plan not found")

        # Determine Stripe price ID based on billing cycle
        if billing_cycle == "yearly":
            # You would need to add yearly price IDs to your plan model
            stripe_price_id = new_plan.stripe_price_id  # For now, use monthly
        else:
            stripe_price_id = new_plan.stripe_price_id

        if not stripe_price_id:
            raise ValueError(f"No Stripe price ID configured for plan: {new_plan.name}")

        # Update subscription in Stripe
        if subscription.stripe_subscription_id:
            proration_behavior = "create_prorations" if prorate else "none"
            stripe_subscription = await StripeService.update_subscription(
                subscription.stripe_subscription_id,
                price_id=stripe_price_id,
                proration_behavior=proration_behavior,
            )

            # Update local subscription
            await BillingService.update_subscription_from_stripe(
                db, subscription, stripe_subscription
            )

        # Update plan reference
        subscription.plan_id = new_plan_id
        await db.flush()

        # Update quotas
        await BillingService.update_quotas_from_plan(db, organization_id, new_plan)

        logger.info(
            "Upgraded subscription",
            extra={
                "organization_id": str(organization_id),
                "old_plan": subscription.plan.name if subscription.plan else None,
                "new_plan": new_plan.name,
            },
        )

        return subscription

    @staticmethod
    async def cancel_subscription(
        db: AsyncSession, organization_id: UUID, immediately: bool = False
    ) -> Subscription:
        """Cancel organization subscription."""
        subscription = await BillingService.get_organization_subscription(db, organization_id)
        if not subscription:
            raise ValueError("Subscription not found")

        if subscription.stripe_subscription_id:
            stripe_subscription = await StripeService.cancel_subscription(
                subscription.stripe_subscription_id, immediately=immediately
            )

            await BillingService.update_subscription_from_stripe(
                db, subscription, stripe_subscription
            )

            logger.info(
                "Canceled subscription",
                extra={
                    "organization_id": str(organization_id),
                    "immediately": immediately,
                },
            )

        return subscription

    @staticmethod
    async def resume_subscription(db: AsyncSession, organization_id: UUID) -> Subscription:
        """Resume a subscription scheduled for cancellation."""
        subscription = await BillingService.get_organization_subscription(db, organization_id)
        if not subscription:
            raise ValueError("Subscription not found")

        if subscription.stripe_subscription_id and subscription.cancel_at_period_end:
            stripe_subscription = await StripeService.resume_subscription(
                subscription.stripe_subscription_id
            )

            await BillingService.update_subscription_from_stripe(
                db, subscription, stripe_subscription
            )

            logger.info(
                "Resumed subscription",
                extra={"organization_id": str(organization_id)},
            )

        return subscription

    # ========================================================================
    # Quota Management
    # ========================================================================

    @staticmethod
    async def update_quotas_from_plan(
        db: AsyncSession, organization_id: UUID, plan: SubscriptionPlan
    ) -> OrganizationQuota:
        """Update organization quotas based on subscription plan."""
        # Get or create quota
        result = await db.execute(
            select(OrganizationQuota).where(
                OrganizationQuota.organization_id == organization_id
            )
        )
        quota = result.scalar_one_or_none()

        if not quota:
            quota = OrganizationQuota(organization_id=organization_id)
            db.add(quota)

        # Update limits from plan
        quota.max_users = plan.max_users
        quota.max_storage_bytes = plan.max_storage_bytes
        quota.max_api_calls_per_month = plan.max_api_calls_per_month
        quota.max_file_uploads_per_day = plan.max_file_uploads_per_day
        quota.max_file_size_bytes = plan.max_file_size_bytes
        quota.last_updated_at = datetime.now(UTC)

        await db.flush()

        logger.info(
            "Updated quotas from plan",
            extra={"organization_id": str(organization_id), "plan": plan.name},
        )

        return quota

    # ========================================================================
    # Payment Method Management
    # ========================================================================

    @staticmethod
    async def save_payment_method(
        db: AsyncSession,
        organization_id: UUID,
        stripe_payment_method: stripe.PaymentMethod,
        is_default: bool = False,
    ) -> PaymentMethod:
        """Save payment method from Stripe to database."""
        payment_method = PaymentMethod(
            organization_id=organization_id,
            stripe_payment_method_id=stripe_payment_method.id,
            type=stripe_payment_method.type,
            is_default=is_default,
        )

        # Extract card details if type is card
        if stripe_payment_method.type == "card":
            card = stripe_payment_method.card
            payment_method.card_brand = card.brand
            payment_method.card_last4 = card.last4
            payment_method.card_exp_month = card.exp_month
            payment_method.card_exp_year = card.exp_year
            payment_method.card_fingerprint = card.fingerprint

        # Extract bank details if type is us_bank_account
        elif stripe_payment_method.type == "us_bank_account":
            bank = stripe_payment_method.us_bank_account
            payment_method.bank_name = bank.bank_name
            payment_method.bank_last4 = bank.last4

        db.add(payment_method)
        await db.flush()

        logger.info(
            "Saved payment method",
            extra={
                "organization_id": str(organization_id),
                "payment_method_id": stripe_payment_method.id,
                "type": stripe_payment_method.type,
            },
        )

        return payment_method

    # ========================================================================
    # Invoice Management
    # ========================================================================

    @staticmethod
    async def save_invoice(
        db: AsyncSession, organization_id: UUID, stripe_invoice: stripe.Invoice
    ) -> Invoice:
        """Save invoice from Stripe to database."""
        # Get subscription if available
        subscription_id = None
        if stripe_invoice.subscription:
            result = await db.execute(
                select(Subscription).where(
                    Subscription.stripe_subscription_id == stripe_invoice.subscription
                )
            )
            subscription = result.scalar_one_or_none()
            if subscription:
                subscription_id = subscription.id

        # Check if invoice already exists
        result = await db.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice.id)
        )
        invoice = result.scalar_one_or_none()

        if invoice:
            # Update existing invoice
            invoice.status = stripe_invoice.status
            invoice.amount_paid = stripe_invoice.amount_paid
            invoice.amount_remaining = stripe_invoice.amount_remaining
            if stripe_invoice.paid_at:
                invoice.paid_at = datetime.fromtimestamp(
                    stripe_invoice.paid_at, tz=UTC
                )
            invoice.updated_at = datetime.now(UTC)
        else:
            # Create new invoice
            invoice = Invoice(
                organization_id=organization_id,
                subscription_id=subscription_id,
                stripe_invoice_id=stripe_invoice.id,
                stripe_customer_id=stripe_invoice.customer,
                invoice_number=stripe_invoice.number,
                status=stripe_invoice.status,
                amount_due=stripe_invoice.amount_due,
                amount_paid=stripe_invoice.amount_paid,
                amount_remaining=stripe_invoice.amount_remaining,
                subtotal=stripe_invoice.subtotal,
                tax=stripe_invoice.tax or 0,
                total=stripe_invoice.total,
                currency=stripe_invoice.currency,
                invoice_pdf=stripe_invoice.invoice_pdf,
                hosted_invoice_url=stripe_invoice.hosted_invoice_url,
                billing_reason=stripe_invoice.billing_reason,
            )

            if stripe_invoice.period_start:
                invoice.period_start = datetime.fromtimestamp(
                    stripe_invoice.period_start, tz=UTC
                )
            if stripe_invoice.period_end:
                invoice.period_end = datetime.fromtimestamp(
                    stripe_invoice.period_end, tz=UTC
                )
            if stripe_invoice.due_date:
                invoice.due_date = datetime.fromtimestamp(
                    stripe_invoice.due_date, tz=UTC
                )
            if stripe_invoice.status_transitions.paid_at:
                invoice.paid_at = datetime.fromtimestamp(
                    stripe_invoice.status_transitions.paid_at, tz=UTC
                )

            invoice.stripe_metadata = dict(stripe_invoice.metadata or {})

            db.add(invoice)

        await db.flush()

        logger.info(
            "Saved invoice",
            extra={
                "organization_id": str(organization_id),
                "invoice_id": stripe_invoice.id,
                "status": stripe_invoice.status,
            },
        )

        return invoice

    # ========================================================================
    # Billing Event Logging
    # ========================================================================

    @staticmethod
    async def log_billing_event(
        db: AsyncSession,
        organization_id: UUID,
        event_type: str,
        event_data: dict,
        stripe_event_id: str | None = None,
        subscription_id: UUID | None = None,
    ) -> BillingEvent:
        """Log a billing event for audit purposes."""
        event = BillingEvent(
            organization_id=organization_id,
            subscription_id=subscription_id,
            event_type=event_type,
            stripe_event_id=stripe_event_id,
            event_data=event_data,
        )

        db.add(event)
        await db.flush()

        return event
