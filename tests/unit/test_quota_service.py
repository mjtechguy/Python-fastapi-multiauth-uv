"""Unit tests for QuotaService with subscription integration."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quota import OrganizationQuota
from app.models.subscription import Subscription
from app.services.quota import QuotaService


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_subscription():
    """Create a sample active subscription."""
    return Subscription(
        id=uuid4(),
        organization_id=uuid4(),
        plan_id=uuid4(),
        stripe_subscription_id="sub_test_123",
        stripe_customer_id="cus_test_123",
        status="active",
        cancel_at_period_end=False,
        current_period_start=datetime.now(UTC),
        current_period_end=datetime.now(UTC) + timedelta(days=30),
    )


@pytest.fixture
def sample_quota():
    """Create a sample quota."""
    return OrganizationQuota(
        id=uuid4(),
        organization_id=uuid4(),
        max_users=10,
        current_users=5,
        max_storage_bytes=10_737_418_240,  # 10 GB
        current_storage_bytes=5_368_709_120,  # 5 GB
        max_api_calls_per_month=10000,
        current_api_calls_this_month=5000,
        max_file_uploads_per_day=100,
        current_file_uploads_today=50,
        max_file_size_bytes=52_428_800,  # 50 MB
    )


@pytest.mark.asyncio
class TestSubscriptionStatusChecks:
    """Test subscription status validation."""

    async def test_check_subscription_active_success(self, mock_db, sample_subscription):
        """Test active subscription passes check."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_subscription
        mock_db.execute.return_value = mock_result

        is_active, error = await QuotaService.check_subscription_active(
            mock_db, sample_subscription.organization_id
        )

        assert is_active is True
        assert error is None

    async def test_check_subscription_trialing_success(self, mock_db, sample_subscription):
        """Test trialing subscription passes check."""
        sample_subscription.status = "trialing"
        sample_subscription.trial_end = datetime.now(UTC) + timedelta(days=7)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_subscription
        mock_db.execute.return_value = mock_result

        is_active, error = await QuotaService.check_subscription_active(
            mock_db, sample_subscription.organization_id
        )

        assert is_active is True
        assert error is None

    async def test_check_subscription_canceled_fails(self, mock_db, sample_subscription):
        """Test canceled subscription fails check."""
        sample_subscription.status = "canceled"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_subscription
        mock_db.execute.return_value = mock_result

        is_active, error = await QuotaService.check_subscription_active(
            mock_db, sample_subscription.organization_id
        )

        assert is_active is False
        assert "canceled" in error.lower()

    async def test_check_subscription_past_due_fails(self, mock_db, sample_subscription):
        """Test past_due subscription fails check."""
        sample_subscription.status = "past_due"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_subscription
        mock_db.execute.return_value = mock_result

        is_active, error = await QuotaService.check_subscription_active(
            mock_db, sample_subscription.organization_id
        )

        assert is_active is False
        assert "payment failed" in error.lower()

    async def test_check_subscription_not_found_fails(self, mock_db):
        """Test missing subscription fails check."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        is_active, error = await QuotaService.check_subscription_active(mock_db, uuid4())

        assert is_active is False
        assert "not found" in error.lower()


@pytest.mark.asyncio
class TestQuotaWithSubscription:
    """Test quota checks with subscription validation."""

    async def test_quota_check_users_within_limit(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test user quota check when within limit."""
        # Mock subscription active
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        # Mock quota
        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result]

        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "users", 1
        )

        assert allowed is True
        assert error is None

    async def test_quota_check_users_at_limit(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test user quota check when at limit."""
        sample_quota.current_users = sample_quota.max_users  # At limit

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result]

        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "users", 1
        )

        assert allowed is False
        assert "limit reached" in error.lower()
        assert "upgrade" in error.lower()

    async def test_quota_check_storage_within_limit(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test storage quota check when within limit."""
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result, MagicMock()]

        file_size = 1_048_576  # 1 MB
        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "storage", file_size
        )

        assert allowed is True
        assert error is None

    async def test_quota_check_storage_exceeds_limit(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test storage quota check when would exceed limit."""
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result, MagicMock()]

        # Try to add 10 GB when already at 5 GB (limit is 10 GB)
        file_size = 10_737_418_240  # 10 GB
        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "storage", file_size
        )

        assert allowed is False
        assert "storage limit" in error.lower()

    async def test_quota_check_api_calls_within_limit(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test API call quota check when within limit."""
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result, MagicMock()]

        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "api_calls", 1
        )

        assert allowed is True
        assert error is None

    async def test_quota_check_file_upload_size_exceeds(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test file upload size exceeds limit."""
        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result, MagicMock()]

        # Try to upload 100 MB file when limit is 50 MB
        file_size = 104_857_600  # 100 MB
        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "file_uploads", file_size
        )

        assert allowed is False
        assert "exceeds limit" in error.lower()

    async def test_quota_check_unlimited_quota(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test unlimited quota (-1) allows operations."""
        sample_quota.max_users = -1  # Unlimited

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        quota_result = MagicMock()
        quota_result.scalar_one_or_none.return_value = sample_quota

        mock_db.execute.side_effect = [sub_result, quota_result]

        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "users", 1
        )

        assert allowed is True
        assert error is None

    async def test_quota_check_fails_on_inactive_subscription(
        self, mock_db, sample_subscription, sample_quota
    ):
        """Test quota check fails when subscription is inactive."""
        sample_subscription.status = "canceled"

        sub_result = MagicMock()
        sub_result.scalar_one_or_none.return_value = sample_subscription

        mock_db.execute.return_value = sub_result

        allowed, error = await QuotaService.check_quota_with_subscription(
            mock_db, sample_subscription.organization_id, "users", 1
        )

        assert allowed is False
        assert error is not None
        # Quota checks shouldn't even be reached


@pytest.mark.asyncio
class TestQuotaResetLogic:
    """Test quota reset logic."""

    async def test_monthly_quota_reset_when_needed(self, mock_db, sample_quota):
        """Test monthly quota resets after 30 days."""
        # Set reset date to 31 days ago
        sample_quota.api_calls_reset_at = datetime.now(UTC) - timedelta(days=31)
        sample_quota.current_api_calls_this_month = 5000

        quota = await QuotaService.check_and_reset_monthly_quotas(mock_db, sample_quota)

        assert quota.current_api_calls_this_month == 0
        # Reset timestamp should be updated (checked via commit/refresh in real impl)

    async def test_daily_quota_reset_when_needed(self, mock_db, sample_quota):
        """Test daily quota resets after 1 day."""
        # Set reset date to 2 days ago
        sample_quota.file_uploads_reset_at = datetime.now(UTC) - timedelta(days=2)
        sample_quota.current_file_uploads_today = 50

        quota = await QuotaService.check_and_reset_daily_quotas(mock_db, sample_quota)

        assert quota.current_file_uploads_today == 0
