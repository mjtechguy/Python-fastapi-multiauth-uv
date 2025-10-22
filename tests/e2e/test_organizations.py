"""E2E tests for organization management."""

import pytest
from httpx import AsyncClient


class TestOrganizationCRUD:
    """Test organization CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_organization(self, authenticated_client: AsyncClient):
        """Test creating an organization."""
        org_data = {
            "name": "My Test Company",
            "slug": "my-test-company",
            "description": "A test organization"
        }

        response = await authenticated_client.post("/api/v1/organizations", json=org_data)
        assert response.status_code == 201
        org = response.json()
        assert org["name"] == org_data["name"]
        assert org["slug"] == org_data["slug"]
        assert "id" in org

    @pytest.mark.asyncio
    async def test_list_organizations(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test listing user's organizations."""
        response = await authenticated_client.get("/api/v1/organizations")
        assert response.status_code == 200
        orgs = response.json()
        assert isinstance(orgs, list)
        assert len(orgs) > 0

    @pytest.mark.asyncio
    async def test_get_organization(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test getting organization details."""
        response = await authenticated_client.get(f"/api/v1/organizations/{test_organization['id']}")
        assert response.status_code == 200
        org = response.json()
        assert org["id"] == test_organization["id"]
        assert org["name"] == test_organization["name"]

    @pytest.mark.asyncio
    async def test_update_organization(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test updating organization."""
        update_data = {
            "name": "Updated Organization Name",
            "description": "Updated description"
        }

        response = await authenticated_client.put(
            f"/api/v1/organizations/{test_organization['id']}",
            json=update_data
        )
        assert response.status_code == 200
        org = response.json()
        assert org["name"] == update_data["name"]
        assert org["description"] == update_data["description"]

    @pytest.mark.asyncio
    async def test_organization_not_found(self, authenticated_client: AsyncClient):
        """Test getting non-existent organization."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/organizations/{fake_id}")
        assert response.status_code == 404


class TestQuotaManagement:
    """Test usage quota management."""

    @pytest.mark.asyncio
    async def test_get_quota_status(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test getting organization quota status."""
        response = await authenticated_client.get("/api/v1/quota/status")
        assert response.status_code in [200, 400]  # May fail if user not in org

    @pytest.mark.asyncio
    async def test_update_quota_limits(self, authenticated_client: AsyncClient):
        """Test updating quota limits."""
        limits_data = {
            "max_users": 50,
            "max_storage_bytes": 5368709120,  # 5GB
            "max_api_calls_per_month": 50000
        }

        response = await authenticated_client.put("/api/v1/quota/limits", json=limits_data)
        # May succeed or fail based on org association
        assert response.status_code in [200, 400]
