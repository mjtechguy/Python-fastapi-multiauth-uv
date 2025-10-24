"""Unit tests for BillingService."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.quota import OrganizationQuota
from app.models.subscription import Subscription
from app.models.subscription_plan import SubscriptionPlan
from app.services.billing_service import BillingService


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_plan():
    """Create a sample subscription plan."""
    return SubscriptionPlan(
        id=uuid4(),
        name="pro",
        display_name="Pro",
        description="Professional plan",
        price_monthly=Decimal("99.00"),
        price_yearly=Decimal("990.00"),
        stripe_price_id="price_test_123",
        stripe_product_id="prod_test_123",
        max_users=50,
        max_storage_bytes=107_374_182_400,  # 100 GB
        max_api_calls_per_month=100000,
        max_file_uploads_per_day=1000,
        max_file_size_bytes=104_857_600,  # 100 MB
        features={"priority_support": True, "advanced_analytics": True},
        tier_level=2,
        is_active=True,
    )


@pytest.fixture
def sample_organization():
    """Create a sample organization."""
    return Organization(
        id=uuid4(),
        name="Test Org",
        slug="test-org",
        owner_id=uuid4(),
        is_active=True,
    )


@pytest.mark.asyncio
class TestSubscriptionPlanManagement:
    """Test subscription plan management methods."""

    async def test_get_plan_by_id(self, mock_db, sample_plan):
        """Test getting plan by ID."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_plan
        mock_db.execute.return_value = mock_result

        plan = await BillingService.get_plan_by_id(mock_db, sample_plan.id)

        assert plan == sample_plan
        assert plan.name == "pro"

    async def test_get_plan_by_name(self, mock_db, sample_plan):
        """Test getting plan by name."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_plan
        mock_db.execute.return_value = mock_result

        plan = await BillingService.get_plan_by_name(mock_db, "pro")

        assert plan == sample_plan
        assert plan.display_name == "Pro"

    async def test_list_active_plans(self, mock_db, sample_plan):
        """Test listing active plans."""
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_plan]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        plans = await BillingService.list_active_plans(mock_db)

        assert len(plans) == 1
        assert plans[0] == sample_plan


@pytest.mark.asyncio
class TestSubscriptionCreation:
    """Test subscription creation methods."""

    async def test_create_free_subscription(self, mock_db, sample_organization):
        """Test creating free subscription."""
        org_id = sample_organization.id
        customer_id = "cus_test_123"

        # Mock free plan
        free_plan = SubscriptionPlan(
            id=uuid4(),
            name="free",
            display_name="Free",
            price_monthly=Decimal("0.00"),
            max_users=3,
            max_storage_bytes=1_073_741_824,
            max_api_calls_per_month=1000,
            max_file_uploads_per_day=10,
            max_file_size_bytes=5_242_880,
            tier_level=0,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = free_plan
        mock_db.execute.return_value = mock_result

        with patch.object(
            BillingService, "update_quotas_from_plan", new=AsyncMock()
        ) as mock_update_quotas:
            subscription = await BillingService.create_free_subscription(
                mock_db, org_id, customer_id
            )

            assert subscription.organization_id == org_id
            assert subscription.stripe_customer_id == customer_id
            assert subscription.status == "active"
            assert subscription.plan_id == free_plan.id

            # Verify quotas were updated
            mock_update_quotas.assert_called_once()

    async def test_create_free_subscription_plan_not_found(self, mock_db):
        """Test creating free subscription when free plan doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Free plan not found"):
            await BillingService.create_free_subscription(
                mock_db, uuid4(), "cus_test_123"
            )


@pytest.mark.asyncio
class TestQuotaManagement:
    """Test quota management methods."""

    async def test_update_quotas_from_plan(self, mock_db, sample_plan, sample_organization):
        """Test updating quotas from plan."""
        org_id = sample_organization.id

        # Mock quota
        quota = OrganizationQuota(
            id=uuid4(),
            organization_id=org_id,
            max_users=10,  # Old value
            max_storage_bytes=10_737_418_240,  # Old value
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = quota
        mock_db.execute.return_value = mock_result

        updated_quota = await BillingService.update_quotas_from_plan(
            mock_db, org_id, sample_plan
        )

        # Verify quotas updated to match plan
        assert updated_quota.max_users == sample_plan.max_users
        assert updated_quota.max_storage_bytes == sample_plan.max_storage_bytes
        assert updated_quota.max_api_calls_per_month == sample_plan.max_api_calls_per_month
        assert updated_quota.max_file_uploads_per_day == sample_plan.max_file_uploads_per_day

    async def test_update_quotas_creates_if_missing(self, mock_db, sample_plan):
        """Test that update creates quota if it doesn't exist."""
        org_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing quota
        mock_db.execute.return_value = mock_result

        updated_quota = await BillingService.update_quotas_from_plan(
            mock_db, org_id, sample_plan
        )

        # Verify new quota created with plan values
        assert updated_quota.organization_id == org_id
        assert updated_quota.max_users == sample_plan.max_users


@pytest.mark.asyncio
class TestSubscriptionUpgrade:
    """Test subscription upgrade logic."""

    async def test_upgrade_subscription_success(self, mock_db, sample_plan):
        """Test successful subscription upgrade."""
        org_id = uuid4()
        old_plan_id = uuid4()
        new_plan_id = sample_plan.id

        # Mock existing subscription
        subscription = Subscription(
            id=uuid4(),
            organization_id=org_id,
            plan_id=old_plan_id,
            stripe_subscription_id="sub_test_123",
            stripe_customer_id="cus_test_123",
            status="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
        )

        # Mock database responses
        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            # First call: get subscription
            if not hasattr(mock_execute_side_effect, "call_count"):
                mock_execute_side_effect.call_count = 0
            mock_execute_side_effect.call_count += 1

            if mock_execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = subscription
            else:
                result.scalar_one_or_none.return_value = sample_plan
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        with patch(
            "app.services.stripe_service.StripeService.update_subscription",
            new=AsyncMock(return_value=MagicMock()),
        ), patch.object(
            BillingService,
            "update_subscription_from_stripe",
            new=AsyncMock(return_value=subscription),
        ), patch.object(
            BillingService,
            "update_quotas_from_plan",
            new=AsyncMock(),
        ) as mock_update_quotas:
            updated_sub = await BillingService.upgrade_subscription(
                mock_db, org_id, new_plan_id, "monthly", True
            )

            assert updated_sub.plan_id == new_plan_id
            mock_update_quotas.assert_called_once()

    async def test_upgrade_subscription_no_subscription(self, mock_db):
        """Test upgrade fails when subscription doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Subscription not found"):
            await BillingService.upgrade_subscription(
                mock_db, uuid4(), uuid4(), "monthly", True
            )

    async def test_upgrade_subscription_plan_not_found(self, mock_db):
        """Test upgrade fails when plan doesn't exist."""
        org_id = uuid4()

        # Mock subscription exists
        subscription = Subscription(
            id=uuid4(),
            organization_id=org_id,
            plan_id=uuid4(),
            stripe_subscription_id="sub_test_123",
            stripe_customer_id="cus_test_123",
            status="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
        )

        def mock_execute_side_effect(*args, **kwargs):
            result = MagicMock()
            if not hasattr(mock_execute_side_effect, "call_count"):
                mock_execute_side_effect.call_count = 0
            mock_execute_side_effect.call_count += 1

            if mock_execute_side_effect.call_count == 1:
                result.scalar_one_or_none.return_value = subscription
            else:
                result.scalar_one_or_none.return_value = None  # Plan not found
            return result

        mock_db.execute.side_effect = mock_execute_side_effect

        with pytest.raises(ValueError, match="Plan not found"):
            await BillingService.upgrade_subscription(
                mock_db, org_id, uuid4(), "monthly", True
            )


@pytest.mark.asyncio
class TestSubscriptionCancellation:
    """Test subscription cancellation."""

    async def test_cancel_subscription_immediate(self, mock_db):
        """Test immediate subscription cancellation."""
        org_id = uuid4()

        subscription = Subscription(
            id=uuid4(),
            organization_id=org_id,
            plan_id=uuid4(),
            stripe_subscription_id="sub_test_123",
            stripe_customer_id="cus_test_123",
            status="active",
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = subscription
        mock_db.execute.return_value = mock_result

        with patch(
            "app.services.stripe_service.StripeService.cancel_subscription",
            new=AsyncMock(return_value=MagicMock()),
        ), patch.object(
            BillingService,
            "update_subscription_from_stripe",
            new=AsyncMock(return_value=subscription),
        ):
            canceled_sub = await BillingService.cancel_subscription(
                mock_db, org_id, immediately=True
            )

            assert canceled_sub == subscription

    async def test_cancel_subscription_at_period_end(self, mock_db):
        """Test cancellation at period end."""
        org_id = uuid4()

        subscription = Subscription(
            id=uuid4(),
            organization_id=org_id,
            plan_id=uuid4(),
            stripe_subscription_id="sub_test_123",
            stripe_customer_id="cus_test_123",
            status="active",
            cancel_at_period_end=False,
            current_period_start=datetime.now(UTC),
            current_period_end=datetime.now(UTC) + timedelta(days=30),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = subscription
        mock_db.execute.return_value = mock_result

        with patch(
            "app.services.stripe_service.StripeService.cancel_subscription",
            new=AsyncMock(return_value=MagicMock(cancel_at_period_end=True)),
        ), patch.object(
            BillingService,
            "update_subscription_from_stripe",
            new=AsyncMock(return_value=subscription),
        ):
            await BillingService.cancel_subscription(
                mock_db, org_id, immediately=False
            )


@pytest.mark.asyncio
class TestBillingEventLogging:
    """Test billing event logging."""

    async def test_log_billing_event(self, mock_db):
        """Test logging a billing event."""
        org_id = uuid4()
        event_type = "subscription.created"
        event_data = {"subscription_id": "sub_test_123"}
        stripe_event_id = "evt_test_123"

        event = await BillingService.log_billing_event(
            mock_db, org_id, event_type, event_data, stripe_event_id
        )

        assert event.organization_id == org_id
        assert event.event_type == event_type
        assert event.event_data == event_data
        assert event.stripe_event_id == stripe_event_id
        assert event.processed is False
