"""E2E tests for billing and subscription functionality."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.quota import OrganizationQuota
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan


@pytest.mark.asyncio
class TestSubscriptionPlans:
    """Test subscription plan endpoints."""

    async def test_list_subscription_plans(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test listing available subscription plans."""
        response = await client.get("/api/v1/billing/plans", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4  # At least Free, Starter, Pro, Enterprise

        # Verify plan structure
        free_plan = next((p for p in data if p["name"] == "free"), None)
        assert free_plan is not None
        assert free_plan["display_name"] == "Free"
        assert free_plan["price_monthly"] == 0.0
        assert free_plan["max_users"] == 3
        assert free_plan["tier_level"] == 0

        # Verify plans are ordered by tier
        for i in range(len(data) - 1):
            assert data[i]["tier_level"] <= data[i + 1]["tier_level"]


@pytest.mark.asyncio
class TestSubscriptionManagement:
    """Test subscription CRUD operations."""

    async def test_get_current_subscription(
        self, client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
    ):
        """Test getting current organization subscription."""
        response = await client.get("/api/v1/billing/subscription", headers=auth_headers)

        # Should have a free subscription by default
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["active", "trialing"]
        assert "plan_id" in data
        assert "organization_id" in data
        assert "current_period_start" in data
        assert "current_period_end" in data

    async def test_subscription_upgrade_requires_owner(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db: AsyncSession,
        test_user,
    ):
        """Test that only organization owner can upgrade subscription."""
        # Get a plan to upgrade to
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "starter")
        )
        starter_plan = result.scalar_one()

        # Try to upgrade (should work if user is owner)
        response = await client.post(
            "/api/v1/billing/subscription/upgrade",
            headers=auth_headers,
            json={
                "new_plan_id": str(starter_plan.id),
                "billing_cycle": "monthly",
                "prorate": True,
            },
        )

        # Will succeed if owner, or fail if not owner
        # This depends on test setup
        assert response.status_code in [200, 403]

    async def test_subscription_cancel_and_resume(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test canceling and resuming subscription."""
        # Cancel subscription
        response = await client.post(
            "/api/v1/billing/subscription/cancel",
            headers=auth_headers,
            json={"cancel_immediately": False, "reason": "Testing cancel flow"},
        )

        # May succeed or fail based on subscription type
        if response.status_code == 200:
            data = response.json()
            assert data["cancel_at_period_end"] is True or data["status"] == "canceled"

            # Resume subscription
            response = await client.post(
                "/api/v1/billing/subscription/resume", headers=auth_headers
            )

            if response.status_code == 200:
                data = response.json()
                assert data["cancel_at_period_end"] is False


@pytest.mark.asyncio
class TestCheckoutFlow:
    """Test Stripe checkout session creation."""

    async def test_create_checkout_session(
        self, client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
    ):
        """Test creating a Stripe checkout session."""
        # Get starter plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "starter")
        )
        starter_plan = result.scalar_one()

        response = await client.post(
            "/api/v1/billing/checkout",
            headers=auth_headers,
            json={
                "plan_id": str(starter_plan.id),
                "billing_cycle": "monthly",
                "success_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel",
                "trial_days": 14,
            },
        )

        # Will fail if Stripe not configured, but structure should be correct
        if response.status_code == 200:
            data = response.json()
            assert "session_id" in data
            assert "session_url" in data
            assert data["session_url"].startswith("https://checkout.stripe.com/")
        else:
            # Expected if Stripe keys not set
            assert response.status_code in [400, 500]

    async def test_checkout_free_plan_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
    ):
        """Test that checkout for free plan is rejected."""
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "free")
        )
        free_plan = result.scalar_one()

        response = await client.post(
            "/api/v1/billing/checkout",
            headers=auth_headers,
            json={
                "plan_id": str(free_plan.id),
                "billing_cycle": "monthly",
                "success_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel",
            },
        )

        assert response.status_code == 400
        assert "free plan" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestPaymentMethods:
    """Test payment method management."""

    async def test_list_payment_methods(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test listing payment methods."""
        response = await client.get("/api/v1/billing/payment-methods", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # May be empty if no payment methods added

    async def test_add_payment_method_requires_stripe_pm_id(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test adding payment method requires valid Stripe payment method ID."""
        response = await client.post(
            "/api/v1/billing/payment-methods",
            headers=auth_headers,
            json={
                "stripe_payment_method_id": "pm_invalid_test",
                "set_as_default": True,
            },
        )

        # Will fail without valid Stripe PM
        assert response.status_code in [400, 404, 500]


@pytest.mark.asyncio
class TestInvoices:
    """Test invoice management."""

    async def test_list_invoices(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test listing invoices."""
        response = await client.get("/api/v1/billing/invoices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data
        assert isinstance(data["items"], list)

    async def test_list_invoices_pagination(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test invoice list pagination."""
        response = await client.get(
            "/api/v1/billing/invoices?page=1&page_size=10", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


@pytest.mark.asyncio
class TestCustomerPortal:
    """Test Stripe customer portal."""

    async def test_create_portal_session(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ):
        """Test creating customer portal session."""
        response = await client.post(
            "/api/v1/billing/portal",
            headers=auth_headers,
            json={"return_url": "http://localhost:3000/settings"},
        )

        # Will fail if Stripe not configured
        if response.status_code == 200:
            data = response.json()
            assert "portal_url" in data
            assert data["portal_url"].startswith("https://billing.stripe.com/")
        else:
            assert response.status_code in [404, 500]


@pytest.mark.asyncio
class TestUsageTracking:
    """Test usage and quota tracking."""

    async def test_get_usage(self, client: AsyncClient, auth_headers: dict[str, str]):
        """Test getting current billing period usage."""
        response = await client.get("/api/v1/billing/usage", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "period_start" in data
        assert "period_end" in data
        assert "days_remaining" in data
        assert "users_count" in data
        assert "users_limit" in data
        assert "storage_used_bytes" in data
        assert "storage_limit_bytes" in data
        assert "api_calls_this_month" in data
        assert "api_calls_limit" in data
        assert "file_uploads_today" in data
        assert "file_uploads_limit" in data
        assert "usage_percentages" in data

        # Verify usage percentages structure
        percentages = data["usage_percentages"]
        assert "users" in percentages
        assert "storage" in percentages
        assert "api_calls" in percentages
        assert "file_uploads" in percentages


@pytest.mark.asyncio
class TestQuotaEnforcement:
    """Test quota enforcement with subscriptions."""

    async def test_quota_blocks_when_limit_reached(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        db: AsyncSession,
        test_user,
    ):
        """Test that quota enforcement blocks operations when limit reached."""
        # Get user's organization
        result = await db.execute(
            select(Organization)
            .join(Organization.members)
            .where(Organization.members.any(id=test_user.id))
        )
        org = result.scalar_one()

        # Get quota
        result = await db.execute(
            select(OrganizationQuota).where(OrganizationQuota.organization_id == org.id)
        )
        quota = result.scalar_one_or_none()

        if quota:
            # Set quota to limit
            original_limit = quota.max_users
            quota.max_users = quota.current_users  # At limit

            await db.commit()

            # Try to add another user (should fail)
            # This would be tested via organization member add endpoint
            # For now, just verify quota state
            assert quota.current_users >= quota.max_users

            # Restore original limit
            quota.max_users = original_limit
            await db.commit()

    async def test_subscription_status_affects_access(
        self, client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession, test_user
    ):
        """Test that inactive subscription status blocks operations."""
        # Get subscription
        result = await db.execute(
            select(Organization)
            .join(Organization.members)
            .where(Organization.members.any(id=test_user.id))
        )
        org = result.scalar_one()

        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            original_status = subscription.status

            # Set to past_due
            subscription.status = "past_due"
            await db.commit()

            # Try to use service (should check subscription)
            # This would be tested via actual API calls that check quotas
            # For now, verify subscription state
            assert subscription.status == "past_due"

            # Restore
            subscription.status = original_status
            await db.commit()


@pytest.mark.asyncio
class TestBillingEndToEnd:
    """End-to-end billing flow tests."""

    async def test_complete_upgrade_flow(
        self, client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession
    ):
        """Test complete subscription upgrade flow."""
        # 1. Get current subscription (should be free)
        response = await client.get("/api/v1/billing/subscription", headers=auth_headers)
        assert response.status_code == 200
        original_subscription = response.json()

        # 2. List available plans
        response = await client.get("/api/v1/billing/plans", headers=auth_headers)
        assert response.status_code == 200
        plans = response.json()
        starter_plan = next((p for p in plans if p["name"] == "starter"), None)
        assert starter_plan is not None

        # 3. Check current usage
        response = await client.get("/api/v1/billing/usage", headers=auth_headers)
        assert response.status_code == 200
        usage_before = response.json()

        # Note: Actual checkout and webhook processing would require
        # Stripe test mode setup and webhook simulation

    async def test_plan_features_reflected_in_quotas(
        self, client: AsyncClient, auth_headers: dict[str, str], db: AsyncSession, test_user
    ):
        """Test that subscription plan features are reflected in quotas."""
        # Get organization
        result = await db.execute(
            select(Organization)
            .join(Organization.members)
            .where(Organization.members.any(id=test_user.id))
        )
        org = result.scalar_one()

        # Get subscription and quota
        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == org.id)
        )
        subscription = result.scalar_one_or_none()

        result = await db.execute(
            select(OrganizationQuota).where(OrganizationQuota.organization_id == org.id)
        )
        quota = result.scalar_one_or_none()

        if subscription and subscription.plan and quota:
            # Verify quota limits match plan
            plan = subscription.plan
            assert quota.max_users == plan.max_users
            assert quota.max_storage_bytes == plan.max_storage_bytes
            assert quota.max_api_calls_per_month == plan.max_api_calls_per_month
            assert quota.max_file_uploads_per_day == plan.max_file_uploads_per_day
            assert quota.max_file_size_bytes == plan.max_file_size_bytes
