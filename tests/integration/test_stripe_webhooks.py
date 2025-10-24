"""Integration tests for Stripe webhook handling."""

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing_event import BillingEvent
from app.models.invoice import Invoice
from app.models.organization import Organization
from app.models.payment_method import PaymentMethod
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan


class TestStripeWebhooks:
    """Test Stripe webhook event handling."""

    @pytest.fixture
    async def test_plan(self, db_session: AsyncSession) -> SubscriptionPlan:
        """Create a test subscription plan."""
        plan = SubscriptionPlan(
            name="Test Plan",
            slug="test-plan",
            description="Test plan for webhooks",
            price_monthly=1000,
            price_yearly=10000,
            stripe_price_id_monthly="price_test_monthly",
            stripe_price_id_yearly="price_test_yearly",
            features={
                "users": 10,
                "storage_gb": 100,
                "api_calls_per_month": 10000,
            },
            is_active=True,
        )
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)
        return plan

    @pytest.fixture
    async def test_organization(self, db_session: AsyncSession) -> Organization:
        """Create a test organization."""
        org = Organization(
            name="Test Org",
            slug="test-org-webhook",
            stripe_customer_id=f"cus_test_{uuid4().hex[:16]}",
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)
        return org

    def create_webhook_signature(self, payload: str, secret: str) -> str:
        """
        Create a valid Stripe webhook signature.

        This mimics Stripe's signature generation for testing purposes.
        In production, Stripe generates this signature.
        """
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{payload}"

        # Note: In real tests, you might use stripe.webhook.generate_test_header_string()
        # which properly creates the signature
        import hashlib
        import hmac

        signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return f"t={timestamp},v1={signature}"

    async def test_missing_signature_header(
        self, client: AsyncClient, test_organization: Organization
    ):
        """Test webhook request without signature header."""
        payload = {"type": "customer.subscription.created"}

        response = await client.post(
            "/api/v1/webhooks/stripe",
            json=payload,
        )

        assert response.status_code == 400
        assert "stripe-signature" in response.json()["detail"].lower()

    async def test_invalid_signature(
        self, client: AsyncClient, test_organization: Organization
    ):
        """Test webhook request with invalid signature."""
        payload = json.dumps({"type": "customer.subscription.created"})

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": "t=1234567890,v1=invalid_signature",
                "content-type": "application/json",
            },
        )

        assert response.status_code == 400
        assert "signature" in response.json()["detail"].lower()

    async def test_subscription_created_webhook(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        test_plan: SubscriptionPlan,
        monkeypatch,
    ):
        """Test handling of subscription.created webhook event."""
        # Create a mock Stripe event
        stripe_subscription_id = f"sub_test_{uuid4().hex[:16]}"

        event_data = {
            "id": f"evt_{uuid4().hex[:24]}",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": stripe_subscription_id,
                    "customer": test_organization.stripe_customer_id,
                    "status": "active",
                    "current_period_start": int(datetime.now(UTC).timestamp()),
                    "current_period_end": int(
                        datetime.now(UTC).timestamp() + 2592000  # +30 days
                    ),
                    "trial_start": None,
                    "trial_end": None,
                    "cancel_at_period_end": False,
                    "metadata": {
                        "organization_id": str(test_organization.id),
                        "plan_id": str(test_plan.id),
                    },
                }
            },
        }

        # Mock stripe webhook signature verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            # Return a mock event object
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {"object": type("obj", (), data["data"]["object"])()})()
                    # Set attributes on the subscription object
                    for key, value in data["data"]["object"].items():
                        setattr(self.data.object, key, value)

            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify subscription was created in database
        result = await db_session.execute(
            select(Subscription).where(
                Subscription.organization_id == test_organization.id
            )
        )
        subscription = result.scalar_one_or_none()

        assert subscription is not None
        assert subscription.stripe_subscription_id == stripe_subscription_id
        assert subscription.status == "active"
        assert subscription.plan_id == test_plan.id

        # Verify billing event was logged
        event_result = await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.organization_id == test_organization.id,
                BillingEvent.event_type == "subscription.created",
            )
        )
        billing_event = event_result.scalar_one_or_none()
        assert billing_event is not None

    async def test_subscription_updated_webhook(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        test_plan: SubscriptionPlan,
        monkeypatch,
    ):
        """Test handling of subscription.updated webhook event."""
        # Create an existing subscription first
        stripe_subscription_id = f"sub_test_{uuid4().hex[:16]}"
        existing_subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=test_plan.id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=test_organization.stripe_customer_id,
            status="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC),
        )
        db_session.add(existing_subscription)
        await db_session.commit()

        event_data = {
            "id": f"evt_{uuid4().hex[:24]}",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": stripe_subscription_id,
                    "customer": test_organization.stripe_customer_id,
                    "status": "active",
                    "current_period_start": int(datetime.now(UTC).timestamp()),
                    "current_period_end": int(
                        datetime.now(UTC).timestamp() + 2592000
                    ),
                    "trial_start": None,
                    "trial_end": None,
                    "cancel_at_period_end": True,  # User cancelled
                    "metadata": {
                        "organization_id": str(test_organization.id),
                        "plan_id": str(test_plan.id),
                    },
                }
            },
        }

        # Mock webhook verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {"object": type("obj", (), data["data"]["object"])()})()
                    for key, value in data["data"]["object"].items():
                        setattr(self.data.object, key, value)
            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200

        # Verify subscription was updated
        await db_session.refresh(existing_subscription)
        assert existing_subscription.cancel_at_period_end is True

    async def test_subscription_deleted_webhook(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        test_plan: SubscriptionPlan,
        monkeypatch,
    ):
        """Test handling of subscription.deleted webhook event."""
        stripe_subscription_id = f"sub_test_{uuid4().hex[:16]}"

        # Create existing subscription
        existing_subscription = Subscription(
            organization_id=test_organization.id,
            plan_id=test_plan.id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=test_organization.stripe_customer_id,
            status="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC),
        )
        db_session.add(existing_subscription)
        await db_session.commit()

        event_data = {
            "id": f"evt_{uuid4().hex[:24]}",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": stripe_subscription_id,
                    "customer": test_organization.stripe_customer_id,
                    "status": "canceled",
                    "current_period_start": int(datetime.now(UTC).timestamp()),
                    "current_period_end": int(datetime.now(UTC).timestamp()),
                    "trial_start": None,
                    "trial_end": None,
                    "cancel_at_period_end": False,
                    "metadata": {
                        "organization_id": str(test_organization.id),
                    },
                }
            },
        }

        # Mock webhook verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {"object": type("obj", (), data["data"]["object"])()})()
                    for key, value in data["data"]["object"].items():
                        setattr(self.data.object, key, value)
            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200

        # Verify subscription status updated to canceled
        await db_session.refresh(existing_subscription)
        assert existing_subscription.status == "canceled"

    async def test_invoice_payment_succeeded_webhook(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        test_plan: SubscriptionPlan,
        monkeypatch,
    ):
        """Test handling of invoice.payment_succeeded webhook event."""
        invoice_id = f"in_test_{uuid4().hex[:16]}"

        event_data = {
            "id": f"evt_{uuid4().hex[:24]}",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": invoice_id,
                    "customer": test_organization.stripe_customer_id,
                    "subscription": f"sub_test_{uuid4().hex[:16]}",
                    "amount_paid": 1000,
                    "currency": "usd",
                    "status": "paid",
                    "hosted_invoice_url": f"https://invoice.stripe.com/{invoice_id}",
                    "invoice_pdf": f"https://invoice.stripe.com/{invoice_id}/pdf",
                    "created": int(datetime.now(UTC).timestamp()),
                    "metadata": {
                        "organization_id": str(test_organization.id),
                    },
                }
            },
        }

        # Mock webhook verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {"object": type("obj", (), data["data"]["object"])()})()
                    for key, value in data["data"]["object"].items():
                        setattr(self.data.object, key, value)
            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200

        # Verify invoice was created/updated in database
        result = await db_session.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == invoice_id)
        )
        invoice = result.scalar_one_or_none()

        assert invoice is not None
        assert invoice.organization_id == test_organization.id
        assert invoice.status == "paid"
        assert invoice.amount_paid == 1000

    async def test_payment_method_attached_webhook(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        monkeypatch,
    ):
        """Test handling of payment_method.attached webhook event."""
        payment_method_id = f"pm_test_{uuid4().hex[:16]}"

        event_data = {
            "id": f"evt_{uuid4().hex[:24]}",
            "type": "payment_method.attached",
            "data": {
                "object": {
                    "id": payment_method_id,
                    "customer": test_organization.stripe_customer_id,
                    "type": "card",
                    "card": {
                        "brand": "visa",
                        "last4": "4242",
                        "exp_month": 12,
                        "exp_year": 2025,
                    },
                    "metadata": {
                        "organization_id": str(test_organization.id),
                    },
                }
            },
        }

        # Mock webhook verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {
                        "object": type("obj", (), {
                            **data["data"]["object"],
                            "card": type("obj", (), data["data"]["object"]["card"])()
                        })()
                    })()
                    for key, value in data["data"]["object"].items():
                        if key != "card":
                            setattr(self.data.object, key, value)
                    self.data.object.card = self.data.object.card
            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200

        # Verify payment method was added
        result = await db_session.execute(
            select(PaymentMethod).where(
                PaymentMethod.stripe_payment_method_id == payment_method_id
            )
        )
        payment_method = result.scalar_one_or_none()

        assert payment_method is not None
        assert payment_method.organization_id == test_organization.id
        assert payment_method.card_brand == "visa"
        assert payment_method.card_last4 == "4242"

    async def test_duplicate_webhook_event(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_organization: Organization,
        test_plan: SubscriptionPlan,
        monkeypatch,
    ):
        """Test that duplicate webhook events are detected and skipped."""
        event_id = f"evt_{uuid4().hex[:24]}"

        # Create a billing event to simulate a previously processed webhook
        existing_event = BillingEvent(
            organization_id=test_organization.id,
            event_type="subscription.created",
            event_data={},
            stripe_event_id=event_id,
        )
        db_session.add(existing_event)
        await db_session.commit()

        event_data = {
            "id": event_id,
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": f"sub_test_{uuid4().hex[:16]}",
                    "customer": test_organization.stripe_customer_id,
                    "status": "active",
                    "current_period_start": int(datetime.now(UTC).timestamp()),
                    "current_period_end": int(
                        datetime.now(UTC).timestamp() + 2592000
                    ),
                    "trial_start": None,
                    "trial_end": None,
                    "cancel_at_period_end": False,
                    "metadata": {
                        "organization_id": str(test_organization.id),
                        "plan_id": str(test_plan.id),
                    },
                }
            },
        }

        # Mock webhook verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {"object": type("obj", (), data["data"]["object"])()})()
                    for key, value in data["data"]["object"].items():
                        setattr(self.data.object, key, value)
            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "duplicate_event"

    async def test_unhandled_webhook_event_type(
        self, client: AsyncClient, test_organization: Organization, monkeypatch
    ):
        """Test that unhandled webhook event types are gracefully ignored."""
        event_data = {
            "id": f"evt_{uuid4().hex[:24]}",
            "type": "charge.refunded",  # Unhandled event type
            "data": {
                "object": {
                    "id": f"ch_test_{uuid4().hex[:16]}",
                    "customer": test_organization.stripe_customer_id,
                }
            },
        }

        # Mock webhook verification
        def mock_construct_webhook_event(payload, sig_header, secret):
            class MockEvent:
                def __init__(self, data):
                    self.id = data["id"]
                    self.type = data["type"]
                    self.data = type("obj", (), {"object": type("obj", (), data["data"]["object"])()})()
                    for key, value in data["data"]["object"].items():
                        setattr(self.data.object, key, value)
            return MockEvent(event_data)

        from app.services import stripe_service
        monkeypatch.setattr(
            stripe_service.StripeService,
            "construct_webhook_event",
            mock_construct_webhook_event,
        )

        payload = json.dumps(event_data)
        signature = self.create_webhook_signature(payload, "whsec_test_secret")

        response = await client.post(
            "/api/v1/webhooks/stripe",
            content=payload,
            headers={
                "stripe-signature": signature,
                "content-type": "application/json",
            },
        )

        # Should succeed but log that the event type is unhandled
        assert response.status_code == 200
        assert response.json()["status"] == "success"
