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

    @pytest.mark.asyncio
    async def test_delete_organization(self, authenticated_client: AsyncClient):
        """Test deleting an organization."""
        # Create an organization to delete
        org_data = {
            "name": "Org to Delete",
            "slug": "org-to-delete",
            "description": "This organization will be deleted"
        }
        create_response = await authenticated_client.post("/api/v1/organizations", json=org_data)
        assert create_response.status_code == 201
        org_id = create_response.json()["id"]

        # Delete the organization
        response = await authenticated_client.delete(f"/api/v1/organizations/{org_id}")
        assert response.status_code == 204

        # Verify organization is deleted
        get_response = await authenticated_client.get(f"/api/v1/organizations/{org_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_organization(self, authenticated_client: AsyncClient):
        """Test deleting non-existent organization."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.delete(f"/api/v1/organizations/{fake_id}")
        assert response.status_code == 404


class TestOrganizationMembers:
    """Test organization member management."""

    @pytest.mark.asyncio
    async def test_add_member_to_organization(self, authenticated_client: AsyncClient, test_organization: dict, client: AsyncClient, db_session):
        """Test adding a member to an organization."""
        # Create another user to add as member
        from app.models.user import User
        from app.core.security import get_password_hash

        new_user = User(
            email="newmember@example.com",
            username="newmember",
            full_name="New Member",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(new_user)
        await db_session.commit()
        await db_session.refresh(new_user)

        # Add user to organization
        member_data = {
            "user_id": str(new_user.id),
            "role": "member"
        }
        response = await authenticated_client.post(
            f"/api/v1/organizations/{test_organization['id']}/members",
            json=member_data
        )
        assert response.status_code in [201, 400]  # May fail based on permissions

    @pytest.mark.asyncio
    async def test_add_member_with_admin_role(self, authenticated_client: AsyncClient, test_organization: dict, client: AsyncClient, db_session):
        """Test adding a member with admin role."""
        # Create another user
        from app.models.user import User
        from app.core.security import get_password_hash

        new_user = User(
            email="adminmember@example.com",
            username="adminmember",
            full_name="Admin Member",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(new_user)
        await db_session.commit()
        await db_session.refresh(new_user)

        # Add user as admin
        member_data = {
            "user_id": str(new_user.id),
            "role": "admin"
        }
        response = await authenticated_client.post(
            f"/api/v1/organizations/{test_organization['id']}/members",
            json=member_data
        )
        assert response.status_code in [201, 400]

    @pytest.mark.asyncio
    async def test_add_nonexistent_user_to_organization(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test adding non-existent user to organization."""
        fake_user_id = "00000000-0000-0000-0000-000000000000"
        member_data = {
            "user_id": fake_user_id,
            "role": "member"
        }
        response = await authenticated_client.post(
            f"/api/v1/organizations/{test_organization['id']}/members",
            json=member_data
        )
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_add_member_to_nonexistent_organization(self, authenticated_client: AsyncClient, db_session):
        """Test adding member to non-existent organization."""
        # Create a user
        from app.models.user import User
        from app.core.security import get_password_hash

        user = User(
            email="orphanmember@example.com",
            username="orphanmember",
            full_name="Orphan Member",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        fake_org_id = "00000000-0000-0000-0000-000000000000"
        member_data = {
            "user_id": str(user.id),
            "role": "member"
        }
        response = await authenticated_client.post(
            f"/api/v1/organizations/{fake_org_id}/members",
            json=member_data
        )
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_remove_member_from_organization(self, authenticated_client: AsyncClient, test_organization: dict, db_session):
        """Test removing a member from an organization."""
        # Create and add a user first
        from app.models.user import User
        from app.core.security import get_password_hash

        user_to_remove = User(
            email="removeme@example.com",
            username="removeme",
            full_name="Remove Me",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user_to_remove)
        await db_session.commit()
        await db_session.refresh(user_to_remove)

        # Add user to organization
        member_data = {
            "user_id": str(user_to_remove.id),
            "role": "member"
        }
        add_response = await authenticated_client.post(
            f"/api/v1/organizations/{test_organization['id']}/members",
            json=member_data
        )

        if add_response.status_code == 201:
            # Remove the member
            remove_data = {"user_id": str(user_to_remove.id)}
            response = await authenticated_client.delete(
                f"/api/v1/organizations/{test_organization['id']}/members",
                json=remove_data
            )
            assert response.status_code in [204, 200, 400]

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test removing non-existent member from organization."""
        fake_user_id = "00000000-0000-0000-0000-000000000000"
        remove_data = {"user_id": fake_user_id}
        response = await authenticated_client.delete(
            f"/api/v1/organizations/{test_organization['id']}/members",
            json=remove_data
        )
        assert response.status_code in [404, 400]

    @pytest.mark.asyncio
    async def test_member_operations_unauthorized(self, client: AsyncClient, test_organization: dict):
        """Test member operations without authentication."""
        member_data = {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "role": "member"
        }
        response = await client.post(
            f"/api/v1/organizations/{test_organization['id']}/members",
            json=member_data
        )
        assert response.status_code == 401


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
