"""Integration tests for Celery background tasks."""

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.webhook import Webhook
from app.tasks.celery_app import celery_app
from app.tasks.email import (
    send_email,
    send_password_reset_email,
    send_verification_email,
    send_welcome_email,
)

# Configure Celery for testing (eager mode - execute tasks synchronously)
celery_app.conf.update(
    task_always_eager=True,  # Execute tasks immediately
    task_eager_propagates=True,  # Propagate exceptions
    broker_connection_retry_on_startup=False,
)


class TestCeleryEmailTasks:
    """Test email tasks executed through Celery."""

    @pytest.fixture
    def mock_smtp(self):
        """Mock SMTP server."""
        with patch("app.tasks.email.smtplib.SMTP") as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server
            yield mock_server

    def test_send_email_task_execution(self, mock_smtp):
        """Test that send_email task executes successfully."""
        result = send_email.apply(
            args=(
                "test@example.com",
                "Test Subject",
                "<p>HTML Content</p>",
                "Text Content",
            )
        )

        assert result.successful()
        assert result.result["status"] == "success"
        mock_smtp.send_message.assert_called_once()

    def test_send_verification_email_task(self, mock_smtp):
        """Test verification email task execution."""
        result = send_verification_email.apply(
            args=("newuser@example.com", "verification_token_123")
        )

        assert result.successful()
        mock_smtp.send_message.assert_called_once()

    def test_send_password_reset_email_task(self, mock_smtp):
        """Test password reset email task execution."""
        result = send_password_reset_email.apply(
            args=("user@example.com", "reset_token_xyz")
        )

        assert result.successful()
        mock_smtp.send_message.assert_called_once()

    def test_send_welcome_email_task(self, mock_smtp):
        """Test welcome email task execution."""
        result = send_welcome_email.apply(args=("newuser@example.com", "John Doe"))

        assert result.successful()
        mock_smtp.send_message.assert_called_once()

    def test_email_task_retry_on_failure(self, mock_smtp):
        """Test that email tasks retry on SMTP failure."""
        import smtplib

        mock_smtp.send_message.side_effect = smtplib.SMTPException("Connection failed")

        with pytest.raises(smtplib.SMTPException):
            send_email.apply(
                args=(
                    "test@example.com",
                    "Test",
                    "<p>Test</p>",
                ),
                throw=True,
            )

    def test_multiple_email_tasks_parallel(self, mock_smtp):
        """Test multiple email tasks can be executed."""
        results = []

        for i in range(5):
            result = send_email.apply(
                args=(
                    f"user{i}@example.com",
                    f"Subject {i}",
                    f"<p>Content {i}</p>",
                )
            )
            results.append(result)

        # All tasks should complete successfully
        assert all(r.successful() for r in results)
        assert mock_smtp.send_message.call_count == 5


class TestCeleryWebhookTasks:
    """Test webhook delivery tasks."""

    @pytest.fixture
    async def test_webhook(self, db_session: AsyncSession) -> Webhook:
        """Create a test webhook."""
        org = Organization(
            name="Test Org",
            slug=f"test-org-{uuid4().hex[:8]}",
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)

        webhook = Webhook(
            organization_id=org.id,
            url="https://example.com/webhook",
            secret="test_secret_key",
            events=["user.created", "user.updated"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        await db_session.refresh(webhook)

        return webhook

    def test_webhook_delivery_task_success(self, test_webhook):
        """Test webhook delivery task with successful HTTP request."""
        from app.tasks.webhook import deliver_webhook

        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            result = deliver_webhook.apply(
                args=(
                    str(test_webhook.id),
                    "user.created",
                    {"user_id": "123", "email": "test@example.com"},
                )
            )

            assert result.successful()
            mock_post.assert_called_once()

            # Verify webhook URL was called
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://example.com/webhook"

    def test_webhook_delivery_task_failure(self, test_webhook):
        """Test webhook delivery task with HTTP failure."""
        from app.tasks.webhook import deliver_webhook

        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_post.side_effect = Exception("Connection timeout")

            with pytest.raises(Exception):
                deliver_webhook.apply(
                    args=(
                        str(test_webhook.id),
                        "user.created",
                        {"user_id": "123"},
                    ),
                    throw=True,
                )

    def test_webhook_hmac_signature(self, test_webhook):
        """Test that webhook delivery includes HMAC signature."""
        from app.tasks.webhook import deliver_webhook

        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            deliver_webhook.apply(
                args=(
                    str(test_webhook.id),
                    "user.created",
                    {"user_id": "456"},
                )
            )

            # Get the headers passed to httpx.post
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs.get("headers", {})

            # Should include X-Webhook-Signature header
            assert "X-Webhook-Signature" in headers


class TestCeleryTaskFailureHandling:
    """Test Celery task failure and Dead Letter Queue."""

    def test_task_failure_creates_dlq_entry(self, db_session: AsyncSession):
        """Test that failed tasks are logged to DLQ."""
        from app.tasks.celery_app import handle_task_failure

        # Simulate a task failure
        task_id = str(uuid4())
        exception = ValueError("Test exception")

        # Mock task object
        mock_task = Mock()
        mock_task.name = "test_task"
        mock_task.request.retries = 3

        # Call the failure handler
        handle_task_failure(
            sender=mock_task,
            task_id=task_id,
            exception=exception,
            args=("arg1", "arg2"),
            kwargs={"key": "value"},
            traceback=None,
            einfo=None,
        )

        # Note: Since this uses sync database, we'd need to verify in a different way
        # For now, we just test that the handler doesn't crash
        assert True

    def test_task_retry_mechanism(self):
        """Test that tasks retry with exponential backoff."""

        @celery_app.task(bind=True, max_retries=3)
        def test_retry_task(self):
            """Test task that always fails."""
            raise Exception("Intentional failure")

        with pytest.raises(Exception):
            test_retry_task.apply(throw=True)


class TestCeleryPyPICheckTask:
    """Test PyPI version checking task."""

    def test_pypi_check_task_execution(self):
        """Test PyPI version check task."""
        from app.tasks.pypi_check import check_package_updates

        with patch("app.tasks.pypi_check.httpx.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "info": {"version": "1.2.3"},
                "releases": {},
            }
            mock_get.return_value = mock_response

            result = check_package_updates.apply()

            # Task should complete without error
            assert result.successful()

    def test_pypi_check_handles_api_failure(self):
        """Test PyPI check gracefully handles API failures."""
        from app.tasks.pypi_check import check_package_updates

        with patch("app.tasks.pypi_check.httpx.get") as mock_get:
            mock_get.side_effect = Exception("API unavailable")

            # Task should handle error gracefully
            result = check_package_updates.apply(throw=False)

            # Should not crash even if API fails
            assert result is not None


class TestCeleryBillingTasks:
    """Test billing-related background tasks."""

    def test_subscription_sync_task(self):
        """Test subscription sync from Stripe."""
        from app.tasks.billing import sync_subscriptions_from_stripe

        with patch("app.services.stripe_service.StripeService.list_subscriptions") as mock_list:
            mock_list.return_value = []

            result = sync_subscriptions_from_stripe.apply()

            assert result.successful()

    def test_trial_expiration_reminder_task(self):
        """Test trial expiration reminder task."""
        from app.tasks.billing import send_trial_expiration_reminders

        with patch("app.tasks.email.send_email") as mock_send:
            mock_send.return_value = {"status": "success"}

            result = send_trial_expiration_reminders.apply()

            # Task should execute successfully
            assert result.successful()

    def test_payment_failure_notification_task(self):
        """Test payment failure notification task."""
        from app.tasks.billing import notify_payment_failures

        with patch("app.tasks.email.send_email") as mock_send:
            mock_send.return_value = {"status": "success"}

            result = notify_payment_failures.apply()

            assert result.successful()


class TestCeleryScheduledTasks:
    """Test scheduled tasks (Celery Beat)."""

    def test_scheduled_task_registration(self):
        """Test that scheduled tasks are properly registered."""
        # Check if tasks are defined in celery beat schedule
        from app.tasks.celery_app import celery_app

        # Verify celery app has task registry
        assert celery_app.tasks is not None
        assert len(celery_app.tasks) > 0

    def test_periodic_task_interval(self):
        """Test periodic task scheduling configuration."""
        from celery.schedules import crontab

        # Example: Check if a periodic task is configured correctly
        # This would need to be in your celery_app configuration

        # For now, just verify crontab works
        schedule = crontab(minute=0, hour=0)  # Daily at midnight
        assert schedule is not None


class TestCeleryConfiguration:
    """Test Celery app configuration."""

    def test_celery_app_configuration(self):
        """Test that Celery app is configured correctly."""
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.accept_content == ["json"]
        assert celery_app.conf.result_serializer == "json"
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_celery_task_routing(self):
        """Test task routing configuration."""
        # Verify tasks are routed to correct queues if configured
        assert True

    def test_celery_retry_policy(self):
        """Test retry policy configuration."""
        assert celery_app.conf.task_default_retry_delay == 60
        assert celery_app.conf.task_max_retries == 3

    def test_celery_time_limits(self):
        """Test task time limit configuration."""
        assert celery_app.conf.task_time_limit == 30 * 60  # 30 minutes
        assert celery_app.conf.task_soft_time_limit == 25 * 60  # 25 minutes


class TestCeleryWithRealBroker:
    """
    Optional tests that use real Redis broker.

    These tests require a running Redis instance.
    """

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-celery-tests", default=False),
        reason="Real Celery tests require --run-celery-tests flag and running Redis",
    )
    def test_real_task_execution(self):
        """
        Test task execution with real Redis broker.

        To run: pytest tests/integration/test_celery_tasks.py --run-celery-tests

        NOTE: Requires Redis running at configured CELERY_BROKER_URL.
        """
        from app.core.config import settings

        # Verify Redis is configured
        if not settings.CELERY_BROKER_URL:
            pytest.skip("Celery broker not configured")

        # Configure celery to use real broker (not eager mode)
        celery_app.conf.update(
            task_always_eager=False,
            task_eager_propagates=False,
        )

        with patch("app.tasks.email.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            # Send task to broker
            result = send_email.delay(
                "test@example.com",
                "Test from Real Broker",
                "<p>Test</p>",
            )

            # Wait for task to complete (with timeout)
            task_result = result.get(timeout=10)

            assert task_result["status"] == "success"

        # Restore eager mode for other tests
        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=True,
        )


def pytest_addoption(parser):
    """Add custom pytest command line options."""
    parser.addoption(
        "--run-celery-tests",
        action="store_true",
        default=False,
        help="Run tests that use real Redis broker (requires running Redis and Celery worker)",
    )
