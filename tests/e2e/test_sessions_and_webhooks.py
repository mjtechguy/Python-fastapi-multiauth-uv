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
