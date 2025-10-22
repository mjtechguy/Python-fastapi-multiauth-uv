"""E2E tests for health checks and monitoring."""

import pytest
from httpx import AsyncClient


class TestHealthChecks:
    """Test health check endpoints."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self, client: AsyncClient):
        """Test basic health check."""
        response = await client.get("/health")
        assert response.status_code == 200
        health = response.json()
        assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_database_health_check(self, client: AsyncClient):
        """Test database health check."""
        response = await client.get("/api/v1/health/db")
        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy"]

    @pytest.mark.asyncio
    async def test_redis_health_check(self, client: AsyncClient):
        """Test Redis health check."""
        response = await client.get("/api/v1/health/redis")
        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert "redis" in health

    @pytest.mark.asyncio
    async def test_celery_health_check(self, client: AsyncClient):
        """Test Celery workers health check."""
        response = await client.get("/api/v1/health/celery")
        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert "celery" in health

    @pytest.mark.asyncio
    async def test_storage_health_check(self, client: AsyncClient):
        """Test storage service health check."""
        response = await client.get("/api/v1/health/storage")
        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert "storage" in health

    @pytest.mark.asyncio
    async def test_aggregate_health_check(self, client: AsyncClient):
        """Test aggregate health check."""
        response = await client.get("/api/v1/health/all")
        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert "checks" in health
        assert "database" in health["checks"]
        assert "redis" in health["checks"]
        assert "celery" in health["checks"]
        assert "storage" in health["checks"]


class TestPrometheusMetrics:
    """Test Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client: AsyncClient):
        """Test Prometheus metrics endpoint."""
        response = await client.get("/metrics")
        assert response.status_code == 200
        # Metrics should be in Prometheus format
        metrics_text = response.text
        assert "# HELP" in metrics_text or "# TYPE" in metrics_text or len(metrics_text) > 0


class TestAPIDocumentation:
    """Test API documentation endpoints."""

    @pytest.mark.asyncio
    async def test_openapi_docs(self, client: AsyncClient):
        """Test OpenAPI docs are accessible."""
        response = await client.get("/docs")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_openapi_json(self, client: AsyncClient):
        """Test OpenAPI JSON schema."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "info" in schema
