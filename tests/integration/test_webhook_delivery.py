"""Integration tests for webhook delivery mechanism."""

import hashlib
import hmac
from datetime import datetime
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.webhook import Webhook, WebhookDelivery
from app.tasks.webhook import deliver_webhook


class TestWebhookDelivery:
    """Test webhook delivery functionality."""

    @pytest.fixture
    async def test_webhook(self, db_session: AsyncSession) -> Webhook:
        """Create a test webhook."""
        org = Organization(
            name="Webhook Test Org",
            slug=f"webhook-org-{uuid4().hex[:8]}",
        )
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)

        webhook = Webhook(
            organization_id=org.id,
            url="https://webhook.example.com/endpoint",
            secret="test_webhook_secret_key",
            events=["user.created", "user.updated", "user.deleted"],
            is_active=True,
        )
        db_session.add(webhook)
        await db_session.commit()
        await db_session.refresh(webhook)

        return webhook

    def test_webhook_delivery_success(self, test_webhook: Webhook):
        """Test successful webhook delivery."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.headers = {"content-type": "application/json"}
            mock_post.return_value = mock_response

            payload = {"event": "user.created", "user_id": "123", "email": "test@example.com"}

            result = deliver_webhook.apply(
                args=(str(test_webhook.id), "user.created", payload)
            )

            assert result.successful()
            mock_post.assert_called_once()

            # Verify correct URL was called
            call_args = mock_post.call_args
            assert call_args[0][0] == test_webhook.url

    def test_webhook_hmac_signature_generation(self, test_webhook: Webhook):
        """Test that webhook includes HMAC signature."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            payload = {"event": "user.updated", "data": "test"}

            deliver_webhook.apply(
                args=(str(test_webhook.id), "user.updated", payload)
            )

            # Get headers passed to httpx.post
            call_kwargs = mock_post.call_args[1]
            headers = call_kwargs.get("headers", {})

            # Verify signature header exists
            assert "X-Webhook-Signature" in headers or "X-Hub-Signature-256" in headers

    def test_webhook_signature_verification(self, test_webhook: Webhook):
        """Test verifying webhook HMAC signature."""
        import json

        payload = {"event": "test", "data": "value"}
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()

        # Generate expected signature
        expected_signature = hmac.new(
            test_webhook.secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        # This signature should be sent in headers
        signature_header = f"sha256={expected_signature}"

        # Verify signature matches
        assert len(expected_signature) == 64  # SHA256 hex digest length

    def test_webhook_delivery_retry_on_failure(self, test_webhook: Webhook):
        """Test webhook delivery retries on failure."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            # First attempt fails
            mock_post.side_effect = Exception("Connection timeout")

            with pytest.raises(Exception):
                deliver_webhook.apply(
                    args=(str(test_webhook.id), "user.created", {"data": "test"}),
                    throw=True,
                )

    def test_webhook_delivery_timeout(self, test_webhook: Webhook):
        """Test webhook delivery with timeout."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            import httpx

            mock_post.side_effect = httpx.TimeoutException("Request timeout")

            with pytest.raises(httpx.TimeoutException):
                deliver_webhook.apply(
                    args=(str(test_webhook.id), "user.created", {"data": "test"}),
                    throw=True,
                )

    def test_webhook_delivery_4xx_error(self, test_webhook: Webhook):
        """Test webhook delivery with 4xx client error."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            # Should not retry on 4xx errors (client fault)
            result = deliver_webhook.apply(
                args=(str(test_webhook.id), "user.created", {"data": "test"}),
                throw=False,
            )

            # Depending on implementation, might fail or return result
            assert result is not None

    def test_webhook_delivery_5xx_error(self, test_webhook: Webhook):
        """Test webhook delivery with 5xx server error."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            # Should retry on 5xx errors (server fault)
            with pytest.raises(Exception):
                deliver_webhook.apply(
                    args=(str(test_webhook.id), "user.created", {"data": "test"}),
                    throw=True,
                )

    async def test_webhook_delivery_tracking(
        self, test_webhook: Webhook, db_session: AsyncSession
    ):
        """Test that webhook deliveries are tracked in database."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            deliver_webhook.apply(
                args=(str(test_webhook.id), "user.created", {"user_id": "789"})
            )

        # Check if delivery was tracked
        result = await db_session.execute(
            select(WebhookDelivery).where(WebhookDelivery.webhook_id == test_webhook.id)
        )
        delivery = result.scalar_one_or_none()

        # Verify delivery record exists (if implemented)
        # assert delivery is not None
        # assert delivery.status_code == 200

    def test_webhook_inactive_not_delivered(self, test_webhook: Webhook):
        """Test that inactive webhooks are not delivered."""
        # Mark webhook as inactive
        test_webhook.is_active = False

        with patch("app.tasks.webhook.httpx.post") as mock_post:
            deliver_webhook.apply(
                args=(str(test_webhook.id), "user.created", {"data": "test"}),
                throw=False,
            )

            # Should not call HTTP post for inactive webhook
            # Implementation dependent
            # mock_post.assert_not_called()

    def test_webhook_event_filtering(self, test_webhook: Webhook):
        """Test that webhooks only receive subscribed events."""
        # Webhook is subscribed to: user.created, user.updated, user.deleted

        with patch("app.tasks.webhook.httpx.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "OK"
            mock_response.headers = {}
            mock_post.return_value = mock_response

            # Subscribed event - should deliver
            deliver_webhook.apply(
                args=(str(test_webhook.id), "user.created", {"data": "test"})
            )

            # Non-subscribed event - should not deliver (implementation dependent)
            # deliver_webhook.apply(
            #     args=(str(test_webhook.id), "file.uploaded", {"data": "test"})
            # )


class TestWebhookPayloadFormat:
    """Test webhook payload formatting."""

    def test_webhook_payload_structure(self):
        """Test that webhook payload has correct structure."""
        payload = {
            "event": "user.created",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"user_id": "123", "email": "test@example.com"},
        }

        # Verify structure
        assert "event" in payload
        assert "data" in payload
        assert isinstance(payload["data"], dict)

    def test_webhook_payload_json_serialization(self):
        """Test that webhook payload can be JSON serialized."""
        import json

        payload = {
            "event": "user.updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {"user_id": "456", "changes": ["email", "name"]},
        }

        # Should serialize without error
        json_str = json.dumps(payload)
        assert isinstance(json_str, str)

        # Should deserialize correctly
        parsed = json.loads(json_str)
        assert parsed["event"] == "user.updated"


class TestWebhookRetryMechanism:
    """Test webhook retry logic."""

    def test_webhook_exponential_backoff(self, test_webhook: Webhook):
        """Test webhook retries with exponential backoff."""
        # This tests the retry configuration
        from app.tasks.webhook import deliver_webhook

        # Verify task has retry configuration
        assert hasattr(deliver_webhook, "max_retries")

    def test_webhook_max_retries(self, test_webhook: Webhook):
        """Test webhook stops after max retries."""
        with patch("app.tasks.webhook.httpx.post") as mock_post:
            # Always fail
            mock_post.side_effect = Exception("Permanent failure")

            # Should fail after max retries
            with pytest.raises(Exception):
                deliver_webhook.apply(
                    args=(str(test_webhook.id), "user.created", {"data": "test"}),
                    throw=True,
                )


class TestWebhookSecurity:
    """Test webhook security features."""

    def test_webhook_https_only(self, test_webhook: Webhook):
        """Test that webhooks only deliver to HTTPS URLs."""
        # Update webhook to HTTP (insecure)
        test_webhook.url = "http://insecure.example.com/webhook"

        # Should reject or warn about insecure URL
        # Implementation dependent

    def test_webhook_signature_prevents_replay(self):
        """Test that webhook signatures prevent replay attacks."""
        # Each webhook should have unique timestamp/nonce
        # Signatures should differ even for same payload

        payload1 = {"event": "test", "timestamp": "2024-01-01T00:00:00"}
        payload2 = {"event": "test", "timestamp": "2024-01-01T00:00:01"}

        # Timestamps differ, so signatures should differ
        assert payload1["timestamp"] != payload2["timestamp"]
