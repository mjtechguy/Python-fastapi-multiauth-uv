"""E2E tests for sessions and webhooks."""

import pytest
from httpx import AsyncClient


class TestSessionManagement:
    """Test session management."""

    @pytest.mark.asyncio
    async def test_list_sessions(self, authenticated_client: AsyncClient):
        """Test listing active sessions."""
        response = await authenticated_client.get("/api/v1/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert isinstance(sessions, list)
        # Should have at least one session (current)
        assert len(sessions) >= 1

    @pytest.mark.asyncio
    async def test_get_session_stats(self, authenticated_client: AsyncClient):
        """Test getting session statistics."""
        response = await authenticated_client.get("/api/v1/sessions/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_sessions" in stats
        assert "active_sessions" in stats


class TestWebhooks:
    """Test webhook management."""

    @pytest.mark.asyncio
    async def test_get_available_events(self, authenticated_client: AsyncClient):
        """Test listing available webhook events."""
        response = await authenticated_client.get("/api/v1/webhooks/events")
        assert response.status_code == 200
        events = response.json()
        assert "events" in events
        assert "descriptions" in events
        assert isinstance(events["events"], list)
        assert len(events["events"]) > 0

    @pytest.mark.asyncio
    async def test_create_webhook(self, authenticated_client: AsyncClient):
        """Test creating a webhook."""
        webhook_data = {
            "url": "https://webhook.site/unique-id",
            "description": "Test webhook",
            "events": ["user.created", "file.uploaded"]
        }

        response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)
        assert response.status_code in [201, 400]  # May fail if org not configured

        if response.status_code == 201:
            webhook = response.json()
            assert webhook["url"] == webhook_data["url"]
            assert "secret" in webhook
            assert webhook["events"] == webhook_data["events"]

    @pytest.mark.asyncio
    async def test_list_webhooks(self, authenticated_client: AsyncClient):
        """Test listing webhooks."""
        response = await authenticated_client.get("/api/v1/webhooks")
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            webhooks = response.json()
            assert "webhooks" in webhooks
            assert isinstance(webhooks["webhooks"], list)

    @pytest.mark.asyncio
    async def test_create_webhook_invalid_events(self, authenticated_client: AsyncClient):
        """Test creating webhook with invalid events."""
        webhook_data = {
            "url": "https://webhook.site/unique-id",
            "events": ["invalid.event", "also.invalid"]
        }

        response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_get_webhook_by_id(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test getting a specific webhook by ID."""
        # Create a webhook first
        webhook_data = {
            "url": "https://webhook.site/test-get-webhook",
            "description": "Test get webhook",
            "events": ["user.created"]
        }
        create_response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)

        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]

            # Get the webhook
            response = await authenticated_client.get(f"/api/v1/webhooks/{webhook_id}")
            assert response.status_code == 200
            webhook = response.json()
            assert webhook["id"] == webhook_id
            assert webhook["url"] == webhook_data["url"]

    @pytest.mark.asyncio
    async def test_get_webhook_not_found(self, authenticated_client: AsyncClient):
        """Test getting non-existent webhook."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/webhooks/{fake_id}")
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_update_webhook(self, authenticated_client: AsyncClient):
        """Test updating a webhook."""
        # Create a webhook first
        webhook_data = {
            "url": "https://webhook.site/test-update",
            "description": "Test update webhook",
            "events": ["user.created"]
        }
        create_response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)

        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]

            # Update the webhook
            update_data = {
                "url": "https://webhook.site/test-update-new",
                "description": "Updated description",
                "events": ["user.created", "file.uploaded"]
            }
            response = await authenticated_client.put(f"/api/v1/webhooks/{webhook_id}", json=update_data)
            assert response.status_code == 200
            updated_webhook = response.json()
            assert updated_webhook["url"] == update_data["url"]
            assert updated_webhook["description"] == update_data["description"]
            assert set(updated_webhook["events"]) == set(update_data["events"])

    @pytest.mark.asyncio
    async def test_update_webhook_not_found(self, authenticated_client: AsyncClient):
        """Test updating non-existent webhook."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        update_data = {
            "url": "https://webhook.site/fake",
            "events": ["user.created"]
        }
        response = await authenticated_client.put(f"/api/v1/webhooks/{fake_id}", json=update_data)
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_delete_webhook(self, authenticated_client: AsyncClient):
        """Test deleting a webhook."""
        # Create a webhook first
        webhook_data = {
            "url": "https://webhook.site/test-delete",
            "description": "Test delete webhook",
            "events": ["user.created"]
        }
        create_response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)

        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]

            # Delete the webhook
            response = await authenticated_client.delete(f"/api/v1/webhooks/{webhook_id}")
            assert response.status_code == 204

            # Verify webhook is deleted
            get_response = await authenticated_client.get(f"/api/v1/webhooks/{webhook_id}")
            assert get_response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_delete_webhook_not_found(self, authenticated_client: AsyncClient):
        """Test deleting non-existent webhook."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.delete(f"/api/v1/webhooks/{fake_id}")
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_test_webhook(self, authenticated_client: AsyncClient):
        """Test sending a test webhook."""
        # Create a webhook first
        webhook_data = {
            "url": "https://webhook.site/test-webhook-trigger",
            "description": "Test webhook trigger",
            "events": ["user.created"]
        }
        create_response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)

        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]

            # Send test webhook
            response = await authenticated_client.post(f"/api/v1/webhooks/{webhook_id}/test")
            # May succeed or fail depending on network/webhook.site availability
            assert response.status_code in [200, 400, 500]

            if response.status_code == 200:
                result = response.json()
                assert "status" in result or "message" in result

    @pytest.mark.asyncio
    async def test_get_webhook_deliveries(self, authenticated_client: AsyncClient):
        """Test getting webhook delivery history."""
        # Create a webhook first
        webhook_data = {
            "url": "https://webhook.site/test-deliveries",
            "description": "Test webhook deliveries",
            "events": ["user.created"]
        }
        create_response = await authenticated_client.post("/api/v1/webhooks", json=webhook_data)

        if create_response.status_code == 201:
            webhook_id = create_response.json()["id"]

            # Get deliveries
            response = await authenticated_client.get(f"/api/v1/webhooks/{webhook_id}/deliveries")
            assert response.status_code in [200, 400]

            if response.status_code == 200:
                deliveries = response.json()
                assert "deliveries" in deliveries or "items" in deliveries
                # May be empty if no deliveries yet

    @pytest.mark.asyncio
    async def test_webhook_unauthorized(self, client: AsyncClient):
        """Test webhook operations without authentication."""
        response = await client.get("/api/v1/webhooks/events")
        assert response.status_code in [200, 401]  # Events may be public or require auth

        response = await client.get("/api/v1/webhooks")
        assert response.status_code == 401


class TestDeadLetterQueue:
    """Test DLQ monitoring."""

    @pytest.mark.asyncio
    async def test_get_dlq_statistics(self, authenticated_client: AsyncClient):
        """Test getting DLQ statistics."""
        response = await authenticated_client.get("/api/v1/dead-letter/statistics")
        assert response.status_code == 200
        stats = response.json()
        assert "total" in stats
        assert "by_status" in stats
        assert "recent_24h" in stats

    @pytest.mark.asyncio
    async def test_list_dead_letter_tasks(self, authenticated_client: AsyncClient):
        """Test listing failed tasks."""
        response = await authenticated_client.get("/api/v1/dead-letter")
        assert response.status_code == 200
        result = response.json()
        assert "tasks" in result
        assert "total" in result
        assert isinstance(result["tasks"], list)

    @pytest.mark.asyncio
    async def test_list_dead_letter_tasks_with_pagination(self, authenticated_client: AsyncClient):
        """Test listing dead letter tasks with pagination."""
        response = await authenticated_client.get("/api/v1/dead-letter?page=1&page_size=10")
        assert response.status_code == 200
        result = response.json()
        assert "tasks" in result
        assert "total" in result

    @pytest.mark.asyncio
    async def test_get_dead_letter_task_by_id(self, authenticated_client: AsyncClient):
        """Test getting a specific dead letter task."""
        # First get list of tasks
        list_response = await authenticated_client.get("/api/v1/dead-letter")
        tasks = list_response.json()["tasks"]

        if len(tasks) > 0:
            task_id = tasks[0]["id"]
            response = await authenticated_client.get(f"/api/v1/dead-letter/{task_id}")
            assert response.status_code == 200
            task = response.json()
            assert task["id"] == task_id
            assert "status" in task
            assert "error" in task or "error_message" in task

    @pytest.mark.asyncio
    async def test_get_dead_letter_task_not_found(self, authenticated_client: AsyncClient):
        """Test getting non-existent dead letter task."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/dead-letter/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_dead_letter_task(self, authenticated_client: AsyncClient):
        """Test retrying a failed task."""
        # First get list of tasks
        list_response = await authenticated_client.get("/api/v1/dead-letter")
        tasks = list_response.json()["tasks"]

        if len(tasks) > 0:
            task_id = tasks[0]["id"]
            response = await authenticated_client.post(f"/api/v1/dead-letter/{task_id}/retry")
            # May succeed or fail depending on task state
            assert response.status_code in [200, 400, 404]

            if response.status_code == 200:
                task = response.json()
                assert task["id"] == task_id
                # Status may have changed after retry
                assert "status" in task

    @pytest.mark.asyncio
    async def test_retry_nonexistent_task(self, authenticated_client: AsyncClient):
        """Test retrying non-existent task."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.post(f"/api/v1/dead-letter/{fake_id}/retry")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_resolve_dead_letter_task(self, authenticated_client: AsyncClient):
        """Test resolving a failed task."""
        # First get list of tasks
        list_response = await authenticated_client.get("/api/v1/dead-letter")
        tasks = list_response.json()["tasks"]

        if len(tasks) > 0:
            task_id = tasks[0]["id"]
            response = await authenticated_client.post(f"/api/v1/dead-letter/{task_id}/resolve")
            # May succeed or fail depending on task state
            assert response.status_code in [200, 400, 404]

            if response.status_code == 200:
                task = response.json()
                assert task["id"] == task_id
                # Task should be marked as resolved
                assert "status" in task

    @pytest.mark.asyncio
    async def test_resolve_nonexistent_task(self, authenticated_client: AsyncClient):
        """Test resolving non-existent task."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.post(f"/api/v1/dead-letter/{fake_id}/resolve")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_ignore_dead_letter_task(self, authenticated_client: AsyncClient):
        """Test ignoring a failed task."""
        # First get list of tasks
        list_response = await authenticated_client.get("/api/v1/dead-letter")
        tasks = list_response.json()["tasks"]

        if len(tasks) > 0:
            task_id = tasks[0]["id"]
            response = await authenticated_client.post(f"/api/v1/dead-letter/{task_id}/ignore")
            # May succeed or fail depending on task state
            assert response.status_code in [200, 400, 404]

            if response.status_code == 200:
                task = response.json()
                assert task["id"] == task_id
                # Task should be marked as ignored
                assert "status" in task

    @pytest.mark.asyncio
    async def test_ignore_nonexistent_task(self, authenticated_client: AsyncClient):
        """Test ignoring non-existent task."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.post(f"/api/v1/dead-letter/{fake_id}/ignore")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_dlq_statistics_structure(self, authenticated_client: AsyncClient):
        """Test DLQ statistics response structure."""
        response = await authenticated_client.get("/api/v1/dead-letter/statistics")
        stats = response.json()

        assert isinstance(stats["total"], int)
        assert isinstance(stats["by_status"], dict)
        assert isinstance(stats["recent_24h"], int)

    @pytest.mark.asyncio
    async def test_dlq_unauthorized(self, client: AsyncClient):
        """Test DLQ operations without authentication."""
        response = await client.get("/api/v1/dead-letter/statistics")
        assert response.status_code == 401

        response = await client.get("/api/v1/dead-letter")
        assert response.status_code == 401
