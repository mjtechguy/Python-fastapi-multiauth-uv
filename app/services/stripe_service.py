"""Stripe service for payment processing."""

from typing import Any

import stripe

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Initialize Stripe with API key
stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_version = settings.STRIPE_API_VERSION


class StripeService:
    """Service for interacting with Stripe API."""

    # ========================================================================
    # Customer Management
    # ========================================================================

    @staticmethod
    async def create_customer(
        email: str,
        name: str | None = None,
        organization_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> stripe.Customer:
        """
        Create a Stripe customer.

        Args:
            email: Customer email
            name: Customer name
            organization_id: Organization UUID (stored in metadata)
            metadata: Additional metadata

        Returns:
            Stripe Customer object
        """
        try:
            customer_metadata = metadata or {}
            if organization_id:
                customer_metadata["organization_id"] = organization_id

            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=customer_metadata,
            )

            logger.info(
                "Created Stripe customer",
                extra={
                    "customer_id": customer.id,
                    "email": email,
                    "organization_id": organization_id,
                },
            )

            return customer

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe customer",
                extra={"email": email, "error": str(e)},
            )
            raise

    @staticmethod
    async def get_customer(customer_id: str) -> stripe.Customer:
        """Get a Stripe customer by ID."""
        try:
            return stripe.Customer.retrieve(customer_id)
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to retrieve Stripe customer",
                extra={"customer_id": customer_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def update_customer(
        customer_id: str,
        email: str | None = None,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> stripe.Customer:
        """Update a Stripe customer."""
        try:
            update_data: dict[str, Any] = {}
            if email:
                update_data["email"] = email
            if name:
                update_data["name"] = name
            if metadata:
                update_data["metadata"] = metadata

            customer = stripe.Customer.modify(customer_id, **update_data)

            logger.info(
                "Updated Stripe customer",
                extra={"customer_id": customer_id, "updates": list(update_data.keys())},
            )

            return customer

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to update Stripe customer",
                extra={"customer_id": customer_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def delete_customer(customer_id: str) -> None:
        """Delete a Stripe customer."""
        try:
            stripe.Customer.delete(customer_id)

            logger.info("Deleted Stripe customer", extra={"customer_id": customer_id})

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to delete Stripe customer",
                extra={"customer_id": customer_id, "error": str(e)},
            )
            raise

    # ========================================================================
    # Subscription Management
    # ========================================================================

    @staticmethod
    async def create_subscription(
        customer_id: str,
        price_id: str,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> stripe.Subscription:
        """
        Create a Stripe subscription.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            trial_period_days: Optional trial period in days
            metadata: Additional metadata

        Returns:
            Stripe Subscription object
        """
        try:
            subscription_data: dict[str, Any] = {
                "customer": customer_id,
                "items": [{"price": price_id}],
                "metadata": metadata or {},
            }

            if trial_period_days:
                subscription_data["trial_period_days"] = trial_period_days

            subscription = stripe.Subscription.create(**subscription_data)

            logger.info(
                "Created Stripe subscription",
                extra={
                    "subscription_id": subscription.id,
                    "customer_id": customer_id,
                    "price_id": price_id,
                    "trial_days": trial_period_days,
                },
            )

            return subscription

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe subscription",
                extra={"customer_id": customer_id, "price_id": price_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def get_subscription(subscription_id: str) -> stripe.Subscription:
        """Get a Stripe subscription by ID."""
        try:
            return stripe.Subscription.retrieve(subscription_id)
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to retrieve Stripe subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def update_subscription(
        subscription_id: str,
        price_id: str | None = None,
        cancel_at_period_end: bool | None = None,
        metadata: dict[str, Any] | None = None,
        proration_behavior: str = "create_prorations",
    ) -> stripe.Subscription:
        """
        Update a Stripe subscription.

        Args:
            subscription_id: Stripe subscription ID
            price_id: New price ID (for plan changes)
            cancel_at_period_end: Whether to cancel at period end
            metadata: Additional metadata
            proration_behavior: How to handle prorations (create_prorations, none, always_invoice)

        Returns:
            Updated Stripe Subscription object
        """
        try:
            update_data: dict[str, Any] = {}

            if price_id:
                # Change subscription plan
                subscription = await StripeService.get_subscription(subscription_id)
                update_data["items"] = [
                    {
                        "id": subscription["items"]["data"][0].id,
                        "price": price_id,
                    }
                ]
                update_data["proration_behavior"] = proration_behavior

            if cancel_at_period_end is not None:
                update_data["cancel_at_period_end"] = cancel_at_period_end

            if metadata:
                update_data["metadata"] = metadata

            subscription = stripe.Subscription.modify(subscription_id, **update_data)

            logger.info(
                "Updated Stripe subscription",
                extra={"subscription_id": subscription_id, "updates": list(update_data.keys())},
            )

            return subscription

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to update Stripe subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def cancel_subscription(
        subscription_id: str, immediately: bool = False
    ) -> stripe.Subscription:
        """
        Cancel a Stripe subscription.

        Args:
            subscription_id: Stripe subscription ID
            immediately: If True, cancel immediately. If False, cancel at period end.

        Returns:
            Canceled Stripe Subscription object
        """
        try:
            if immediately:
                subscription = stripe.Subscription.delete(subscription_id)
                logger.info(
                    "Canceled Stripe subscription immediately",
                    extra={"subscription_id": subscription_id},
                )
            else:
                subscription = stripe.Subscription.modify(
                    subscription_id, cancel_at_period_end=True
                )
                logger.info(
                    "Scheduled Stripe subscription cancellation",
                    extra={"subscription_id": subscription_id},
                )

            return subscription

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to cancel Stripe subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def resume_subscription(subscription_id: str) -> stripe.Subscription:
        """Resume a subscription scheduled for cancellation."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=False
            )

            logger.info(
                "Resumed Stripe subscription",
                extra={"subscription_id": subscription_id},
            )

            return subscription

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to resume Stripe subscription",
                extra={"subscription_id": subscription_id, "error": str(e)},
            )
            raise

    # ========================================================================
    # Payment Method Management
    # ========================================================================

    @staticmethod
    async def attach_payment_method(
        payment_method_id: str, customer_id: str
    ) -> stripe.PaymentMethod:
        """Attach a payment method to a customer."""
        try:
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id, customer=customer_id
            )

            logger.info(
                "Attached payment method to customer",
                extra={"payment_method_id": payment_method_id, "customer_id": customer_id},
            )

            return payment_method

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to attach payment method",
                extra={
                    "payment_method_id": payment_method_id,
                    "customer_id": customer_id,
                    "error": str(e),
                },
            )
            raise

    @staticmethod
    async def detach_payment_method(payment_method_id: str) -> stripe.PaymentMethod:
        """Detach a payment method from a customer."""
        try:
            payment_method = stripe.PaymentMethod.detach(payment_method_id)

            logger.info(
                "Detached payment method",
                extra={"payment_method_id": payment_method_id},
            )

            return payment_method

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to detach payment method",
                extra={"payment_method_id": payment_method_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def set_default_payment_method(
        customer_id: str, payment_method_id: str
    ) -> stripe.Customer:
        """Set default payment method for a customer."""
        try:
            customer = stripe.Customer.modify(
                customer_id,
                invoice_settings={"default_payment_method": payment_method_id},
            )

            logger.info(
                "Set default payment method",
                extra={"customer_id": customer_id, "payment_method_id": payment_method_id},
            )

            return customer

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to set default payment method",
                extra={
                    "customer_id": customer_id,
                    "payment_method_id": payment_method_id,
                    "error": str(e),
                },
            )
            raise

    @staticmethod
    async def list_payment_methods(
        customer_id: str, type: str = "card"
    ) -> list[stripe.PaymentMethod]:
        """List payment methods for a customer."""
        try:
            payment_methods = stripe.PaymentMethod.list(customer=customer_id, type=type)
            return payment_methods.data

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to list payment methods",
                extra={"customer_id": customer_id, "error": str(e)},
            )
            raise

    # ========================================================================
    # Checkout Session
    # ========================================================================

    @staticmethod
    async def create_checkout_session(
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_period_days: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> stripe.checkout.Session:
        """
        Create a Stripe Checkout session for subscription.

        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            trial_period_days: Optional trial period
            metadata: Additional metadata

        Returns:
            Stripe Checkout Session object
        """
        try:
            session_data: dict[str, Any] = {
                "customer": customer_id,
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata or {},
            }

            if trial_period_days:
                session_data["subscription_data"] = {
                    "trial_period_days": trial_period_days
                }

            session = stripe.checkout.Session.create(**session_data)

            logger.info(
                "Created Stripe Checkout session",
                extra={
                    "session_id": session.id,
                    "customer_id": customer_id,
                    "price_id": price_id,
                },
            )

            return session

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe Checkout session",
                extra={"customer_id": customer_id, "price_id": price_id, "error": str(e)},
            )
            raise

    # ========================================================================
    # Customer Portal
    # ========================================================================

    @staticmethod
    async def create_portal_session(
        customer_id: str, return_url: str
    ) -> stripe.billing_portal.Session:
        """
        Create a Stripe Customer Portal session.

        Args:
            customer_id: Stripe customer ID
            return_url: URL to redirect when customer leaves portal

        Returns:
            Stripe Portal Session object
        """
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id, return_url=return_url
            )

            logger.info(
                "Created Stripe Portal session",
                extra={"session_id": session.id, "customer_id": customer_id},
            )

            return session

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to create Stripe Portal session",
                extra={"customer_id": customer_id, "error": str(e)},
            )
            raise

    # ========================================================================
    # Invoice Management
    # ========================================================================

    @staticmethod
    async def get_invoice(invoice_id: str) -> stripe.Invoice:
        """Get a Stripe invoice by ID."""
        try:
            return stripe.Invoice.retrieve(invoice_id)
        except stripe.error.StripeError as e:
            logger.error(
                "Failed to retrieve Stripe invoice",
                extra={"invoice_id": invoice_id, "error": str(e)},
            )
            raise

    @staticmethod
    async def list_invoices(
        customer_id: str, limit: int = 10
    ) -> list[stripe.Invoice]:
        """List invoices for a customer."""
        try:
            invoices = stripe.Invoice.list(customer=customer_id, limit=limit)
            return invoices.data

        except stripe.error.StripeError as e:
            logger.error(
                "Failed to list Stripe invoices",
                extra={"customer_id": customer_id, "error": str(e)},
            )
            raise

    # ========================================================================
    # Webhook Verification
    # ========================================================================

    @staticmethod
    def construct_webhook_event(
        payload: bytes, sig_header: str, webhook_secret: str
    ) -> stripe.Event:
        """
        Verify and construct webhook event from Stripe.

        Args:
            payload: Raw request body bytes
            sig_header: Stripe signature header
            webhook_secret: Webhook secret from Stripe

        Returns:
            Stripe Event object

        Raises:
            ValueError: Invalid payload
            stripe.error.SignatureVerificationError: Invalid signature
        """
        try:
            return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)

        except ValueError as e:
            logger.error("Invalid webhook payload", extra={"error": str(e)})
            raise

        except stripe.error.SignatureVerificationError as e:
            logger.error("Invalid webhook signature", extra={"error": str(e)})
            raise
