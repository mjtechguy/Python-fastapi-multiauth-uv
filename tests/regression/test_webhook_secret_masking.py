"""Regression test for webhook secret masking fix.

Issue: Webhook responses exposed full secrets in all API responses,
creating a security vulnerability. Secrets should only be shown once
during creation.

Fix: Created two response schemas:
- WebhookCreatedResponse: Returns full secret only on creation
- WebhookResponse: Returns masked secret (first 8 chars + asterisks)
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.webhook import Webhook


@pytest.mark.asyncio
class TestWebhookSecretMasking:
    """Test that webhook secrets are properly masked in API responses."""

    async def test_webhook_creation_returns_full_secret(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that creating a webhook returns the full secret once.

        This is the only time the full secret should be visible.
        """
        # Create a webhook
        response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook",
                "description": "Test webhook for secret masking",
                "events": ["user.created", "user.updated"],
            },
        )

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()

        # Should have a secret field
        assert "secret" in data, "Response should include secret"
        secret = data["secret"]

        # Secret should be long and not masked
        assert len(secret) > 20, f"Secret should be substantial length, got {len(secret)}"
        assert "*" not in secret, "Secret should NOT be masked on creation"

        # Verify the secret is stored correctly in database
        result = await db_session.execute(
            select(Webhook).where(Webhook.id == data["id"])
        )
        webhook = result.scalar_one()
        assert webhook.secret == secret, "Stored secret should match returned secret"

    async def test_webhook_list_returns_masked_secrets(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that listing webhooks returns masked secrets.

        Secrets should show only first 8 characters + asterisks.
        """
        # Create a webhook (get full secret)
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-list",
                "description": "Test list masking",
                "events": ["file.uploaded"],
            },
        )
        full_secret = create_response.json()["secret"]

        # List webhooks
        list_response = await authenticated_client.get("/api/v1/webhooks?page=1&page_size=10")

        assert list_response.status_code == 200
        data = list_response.json()

        # Find our webhook in the list
        webhooks = data["webhooks"]
        our_webhook = next(
            (w for w in webhooks if w["url"] == "https://example.com/webhook-list"),
            None
        )

        assert our_webhook is not None, "Webhook should be in list"

        # Secret should be masked
        masked_secret = our_webhook["secret"]
        assert masked_secret != full_secret, "Secret should be masked in list"
        assert masked_secret.startswith(full_secret[:8]), \
            f"Masked secret should start with first 8 chars: {masked_secret}"
        assert "*" in masked_secret, "Masked secret should contain asterisks"

    async def test_webhook_get_returns_masked_secret(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that retrieving a specific webhook returns masked secret.
        """
        # Create a webhook
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-get",
                "description": "Test get masking",
                "events": ["user.login"],
            },
        )
        webhook_id = create_response.json()["id"]
        full_secret = create_response.json()["secret"]

        # Get specific webhook
        get_response = await authenticated_client.get(f"/api/v1/webhooks/{webhook_id}")

        assert get_response.status_code == 200
        data = get_response.json()

        # Secret should be masked
        masked_secret = data["secret"]
        assert masked_secret != full_secret, "Secret should be masked on GET"
        assert masked_secret.startswith(full_secret[:8]), \
            "Masked secret should show first 8 chars"
        assert "*" in masked_secret, "Masked secret should contain asterisks"

    async def test_masked_secret_format(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test the exact format of masked secrets.

        Format should be: first_8_chars + ('*' * remaining_length)
        """
        # Create a webhook
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-format",
                "description": "Test masking format",
                "events": ["test.event"],
            },
        )
        full_secret = create_response.json()["secret"]
        webhook_id = create_response.json()["id"]

        # Get the webhook
        get_response = await authenticated_client.get(f"/api/v1/webhooks/{webhook_id}")
        masked_secret = get_response.json()["secret"]

        # Verify format
        expected_visible = full_secret[:8]
        expected_masked_length = len(full_secret) - 8
        expected_masked = f"{expected_visible}{'*' * expected_masked_length}"

        assert masked_secret == expected_masked, \
            f"Expected '{expected_masked}', got '{masked_secret}'"

    async def test_webhook_update_does_not_change_secret(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that updating a webhook doesn't change or expose the secret.
        """
        # Create a webhook
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-update",
                "description": "Test update secret",
                "events": ["user.created"],
            },
        )
        webhook_id = create_response.json()["id"]
        original_secret = create_response.json()["secret"]

        # Update the webhook
        update_response = await authenticated_client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={
                "url": "https://example.com/webhook-updated",
                "description": "Updated description",
            },
        )

        assert update_response.status_code == 200
        data = update_response.json()

        # Secret should be masked (not full secret)
        assert data["secret"] != original_secret, "Secret should be masked after update"
        assert "*" in data["secret"], "Secret should contain asterisks"

        # Verify secret in database hasn't changed
        result = await db_session.execute(
            select(Webhook).where(Webhook.id == webhook_id)
        )
        webhook = result.scalar_one()
        assert webhook.secret == original_secret, "Secret in DB should not change on update"

    async def test_multiple_webhooks_each_have_masked_secrets(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that multiple webhooks each have properly masked secrets.
        """
        # Create 3 webhooks
        webhooks_data = []
        for i in range(3):
            response = await authenticated_client.post(
                "/api/v1/webhooks",
                json={
                    "url": f"https://example.com/webhook-{i}",
                    "description": f"Webhook {i}",
                    "events": ["test.event"],
                },
            )
            webhooks_data.append({
                "id": response.json()["id"],
                "full_secret": response.json()["secret"],
                "url": f"https://example.com/webhook-{i}",
            })

        # List all webhooks
        list_response = await authenticated_client.get("/api/v1/webhooks?page=1&page_size=10")
        webhooks = list_response.json()["webhooks"]

        # Verify each webhook has masked secret
        for wh_data in webhooks_data:
            webhook_in_list = next(
                (w for w in webhooks if w["id"] == wh_data["id"]),
                None
            )
            assert webhook_in_list is not None

            masked_secret = webhook_in_list["secret"]
            full_secret = wh_data["full_secret"]

            # Should be masked
            assert masked_secret != full_secret
            assert masked_secret.startswith(full_secret[:8])
            assert "*" in masked_secret

    async def test_webhook_deliveries_do_not_expose_secret(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that webhook delivery history doesn't expose the secret.
        """
        # Create a webhook
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-deliveries",
                "description": "Test deliveries",
                "events": ["test.event"],
            },
        )
        webhook_id = create_response.json()["id"]
        full_secret = create_response.json()["secret"]

        # Get webhook deliveries
        deliveries_response = await authenticated_client.get(
            f"/api/v1/webhooks/{webhook_id}/deliveries?page=1&page_size=10"
        )

        assert deliveries_response.status_code == 200
        data = deliveries_response.json()

        # Deliveries should not contain the secret at all
        deliveries_json = str(data)
        assert full_secret not in deliveries_json, \
            "Full secret should not appear in deliveries response"

    async def test_regression_secret_exposure_fixed(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Regression test: Verify that the secret exposure vulnerability is fixed.

        Before the fix, ALL responses (list, get, update) exposed the full secret.
        After the fix, only creation exposes the full secret.
        """
        # Create a webhook and save the full secret
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-regression",
                "description": "Regression test",
                "events": ["user.created"],
            },
        )
        full_secret = create_response.json()["secret"]
        webhook_id = create_response.json()["id"]

        # All subsequent operations should return MASKED secrets
        operations = [
            ("GET list", authenticated_client.get("/api/v1/webhooks?page=1&page_size=10")),
            ("GET single", authenticated_client.get(f"/api/v1/webhooks/{webhook_id}")),
            ("PUT update", authenticated_client.put(
                f"/api/v1/webhooks/{webhook_id}",
                json={"is_active": True}
            )),
        ]

        for operation_name, response_coro in operations:
            response = await response_coro
            assert response.status_code in [200, 201], \
                f"{operation_name} should succeed"

            response_text = response.text
            # Full secret should NOT appear in response
            # Note: We check the response text, not just the JSON,
            # to ensure it's not hidden anywhere
            secret_exposed = full_secret in response_text

            assert not secret_exposed, \
                f"{operation_name} should NOT expose full secret, but it did!"

    async def test_secret_only_shown_once_on_creation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test the complete flow: secret shown once on creation, never again.

        This is the primary security requirement.
        """
        # 1. Create webhook - should get full secret
        create_response = await authenticated_client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook-once",
                "description": "Test secret shown once",
                "events": ["user.login"],
            },
        )
        assert create_response.status_code == 201
        full_secret = create_response.json()["secret"]
        webhook_id = create_response.json()["id"]

        # Verify it's a real secret (not masked)
        assert len(full_secret) > 20
        assert "*" not in full_secret

        # 2. From this point on, secret should ALWAYS be masked

        # Get webhook by ID
        get_response = await authenticated_client.get(f"/api/v1/webhooks/{webhook_id}")
        assert "*" in get_response.json()["secret"]

        # List webhooks
        list_response = await authenticated_client.get("/api/v1/webhooks?page=1&page_size=10")
        webhook_in_list = next(
            (w for w in list_response.json()["webhooks"] if w["id"] == webhook_id),
            None
        )
        assert webhook_in_list is not None
        assert "*" in webhook_in_list["secret"]

        # Update webhook
        update_response = await authenticated_client.put(
            f"/api/v1/webhooks/{webhook_id}",
            json={"description": "Updated"}
        )
        assert "*" in update_response.json()["secret"]

        # Test webhook
        test_response = await authenticated_client.post(
            f"/api/v1/webhooks/{webhook_id}/test",
            json={"event_type": "test.event"}
        )
        # Test response might not include webhook details, but if it does,
        # the secret should be masked
        if "webhook" in test_response.json():
            assert "*" in test_response.json()["webhook"]["secret"]

    async def test_first_eight_characters_are_sufficient_for_identification(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """
        Test that showing first 8 chars allows webhook identification
        without compromising security.
        """
        # Create multiple webhooks
        secrets = []
        for i in range(5):
            response = await authenticated_client.post(
                "/api/v1/webhooks",
                json={
                    "url": f"https://example.com/webhook-id-{i}",
                    "description": f"Webhook {i}",
                    "events": ["test.event"],
                },
            )
            secrets.append(response.json()["secret"])

        # All secrets should be unique
        assert len(set(secrets)) == 5, "All secrets should be unique"

        # First 8 chars should also be unique (for identification)
        first_eight = [s[:8] for s in secrets]
        assert len(set(first_eight)) == 5, \
            "First 8 chars should be unique enough for identification"

        # List webhooks and verify each is identifiable
        list_response = await authenticated_client.get("/api/v1/webhooks?page=1&page_size=10")
        webhooks = list_response.json()["webhooks"]

        # Each webhook should be identifiable by its first 8 chars
        for secret in secrets:
            matching_webhook = next(
                (w for w in webhooks if w["secret"].startswith(secret[:8])),
                None
            )
            assert matching_webhook is not None, \
                f"Should be able to identify webhook by first 8 chars: {secret[:8]}"
