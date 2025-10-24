"""E2E tests for team management endpoints."""

import pytest
from httpx import AsyncClient


class TestTeamCRUD:
    """Test team CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_team(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test creating a team."""
        team_data = {
            "name": "Engineering Team",
            "slug": "engineering-team",
            "description": "Software engineering team",
            "organization_id": test_organization["id"]
        }

        response = await authenticated_client.post("/api/v1/teams", json=team_data)
        assert response.status_code == 201
        team = response.json()
        assert team["name"] == team_data["name"]
        assert team["slug"] == team_data["slug"]
        assert team["organization_id"] == test_organization["id"]
        assert "id" in team

    @pytest.mark.asyncio
    async def test_create_team_duplicate_slug(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test creating team with duplicate slug in same organization."""
        team_data = {
            "name": "Team One",
            "slug": "duplicate-slug",
            "organization_id": test_organization["id"]
        }

        # Create first team
        response1 = await authenticated_client.post("/api/v1/teams", json=team_data)
        assert response1.status_code == 201

        # Try to create second team with same slug
        team_data["name"] = "Team Two"
        response2 = await authenticated_client.post("/api/v1/teams", json=team_data)
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_create_team_nonexistent_organization(self, authenticated_client: AsyncClient):
        """Test creating team in non-existent organization."""
        team_data = {
            "name": "Orphan Team",
            "slug": "orphan-team",
            "organization_id": "00000000-0000-0000-0000-000000000000"
        }

        response = await authenticated_client.post("/api/v1/teams", json=team_data)
        assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_create_team_unauthorized(self, client: AsyncClient, test_organization: dict):
        """Test creating team without authentication."""
        team_data = {
            "name": "Team",
            "slug": "team",
            "organization_id": test_organization["id"]
        }

        response = await client.post("/api/v1/teams", json=team_data)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_teams_in_organization(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test listing teams in an organization."""
        # Create a team first
        team_data = {
            "name": "Test Team",
            "slug": "test-team",
            "organization_id": test_organization["id"]
        }
        await authenticated_client.post("/api/v1/teams", json=team_data)

        # List teams in organization
        response = await authenticated_client.get(
            f"/api/v1/teams?organization_id={test_organization['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_user_teams(self, authenticated_client: AsyncClient):
        """Test listing teams user is a member of."""
        response = await authenticated_client.get("/api/v1/teams")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_teams_with_pagination(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test team listing with pagination."""
        response = await authenticated_client.get(
            f"/api/v1/teams?organization_id={test_organization['id']}&page=1&page_size=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_team(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test getting team details."""
        # Create a team
        team_data = {
            "name": "Get Test Team",
            "slug": "get-test-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Get team
        response = await authenticated_client.get(f"/api/v1/teams/{team_id}")
        assert response.status_code == 200
        team = response.json()
        assert team["id"] == team_id
        assert team["name"] == team_data["name"]
        assert "member_count" in team

    @pytest.mark.asyncio
    async def test_get_team_not_found(self, authenticated_client: AsyncClient):
        """Test getting non-existent team."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/teams/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_team(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test updating team."""
        # Create a team
        team_data = {
            "name": "Update Test Team",
            "slug": "update-test-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Update team
        update_data = {
            "name": "Updated Team Name",
            "description": "Updated description"
        }
        response = await authenticated_client.put(f"/api/v1/teams/{team_id}", json=update_data)
        assert response.status_code == 200
        team = response.json()
        assert team["name"] == update_data["name"]
        assert team["description"] == update_data["description"]

    @pytest.mark.asyncio
    async def test_update_team_not_found(self, authenticated_client: AsyncClient):
        """Test updating non-existent team."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        update_data = {"name": "New Name"}
        response = await authenticated_client.put(f"/api/v1/teams/{fake_id}", json=update_data)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_team(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test deleting a team."""
        # Create a team
        team_data = {
            "name": "Delete Test Team",
            "slug": "delete-test-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Delete team
        response = await authenticated_client.delete(f"/api/v1/teams/{team_id}")
        assert response.status_code == 204

        # Verify team is deleted
        get_response = await authenticated_client.get(f"/api/v1/teams/{team_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_team_not_found(self, authenticated_client: AsyncClient):
        """Test deleting non-existent team."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.delete(f"/api/v1/teams/{fake_id}")
        assert response.status_code == 404


class TestTeamMembers:
    """Test team member management."""

    @pytest.mark.asyncio
    async def test_add_member_to_team(self, authenticated_client: AsyncClient, test_organization: dict, db_session):
        """Test adding a member to a team."""
        # Create a team
        team_data = {
            "name": "Members Test Team",
            "slug": "members-test-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Create another user and add to organization
        from app.core.security import get_password_hash
        from app.models.user import User

        new_user = User(
            email="teammember@example.com",
            username="teammember",
            full_name="Team Member",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(new_user)
        await db_session.commit()
        await db_session.refresh(new_user)

        # Add user to organization first
        from app.services.organization import OrganizationService
        await OrganizationService.add_member(db_session, test_organization["id"], new_user.id)
        await db_session.commit()

        # Add user to team
        member_data = {"user_id": str(new_user.id)}
        response = await authenticated_client.post(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_add_member_already_in_team(self, authenticated_client: AsyncClient, test_organization: dict, db_session):
        """Test adding a member who is already in the team."""
        # Create a team
        team_data = {
            "name": "Duplicate Member Team",
            "slug": "duplicate-member-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Create and add user to org
        from app.core.security import get_password_hash
        from app.models.user import User
        from app.services.organization import OrganizationService

        user = User(
            email="duplicatemember@example.com",
            username="duplicatemember",
            full_name="Duplicate Member",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        await OrganizationService.add_member(db_session, test_organization["id"], user.id)
        await db_session.commit()

        # Add to team first time
        member_data = {"user_id": str(user.id)}
        response1 = await authenticated_client.post(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response1.status_code == 201

        # Try to add again
        response2 = await authenticated_client.post(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_add_nonexistent_user_to_team(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test adding non-existent user to team."""
        # Create a team
        team_data = {
            "name": "Nonexistent User Team",
            "slug": "nonexistent-user-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Try to add non-existent user
        member_data = {"user_id": "00000000-0000-0000-0000-000000000000"}
        response = await authenticated_client.post(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_add_user_not_in_organization(self, authenticated_client: AsyncClient, test_organization: dict, db_session):
        """Test adding user who is not in the organization."""
        # Create a team
        team_data = {
            "name": "Not In Org Team",
            "slug": "not-in-org-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Create user but don't add to organization
        from app.core.security import get_password_hash
        from app.models.user import User

        user = User(
            email="notinorg@example.com",
            username="notinorg",
            full_name="Not In Org",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Try to add to team
        member_data = {"user_id": str(user.id)}
        response = await authenticated_client.post(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_remove_member_from_team(self, authenticated_client: AsyncClient, test_organization: dict, db_session):
        """Test removing a member from a team."""
        # Create a team
        team_data = {
            "name": "Remove Member Team",
            "slug": "remove-member-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Create and add user to org and team
        from app.core.security import get_password_hash
        from app.models.user import User
        from app.services.organization import OrganizationService

        user = User(
            email="removeme@example.com",
            username="removeme",
            full_name="Remove Me",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        await OrganizationService.add_member(db_session, test_organization["id"], user.id)
        await db_session.commit()

        # Add to team
        member_data = {"user_id": str(user.id)}
        await authenticated_client.post(f"/api/v1/teams/{team_id}/members", json=member_data)

        # Remove from team
        response = await authenticated_client.delete(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_remove_nonexistent_member(self, authenticated_client: AsyncClient, test_organization: dict):
        """Test removing user who is not a team member."""
        # Create a team
        team_data = {
            "name": "No Such Member Team",
            "slug": "no-such-member-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Try to remove non-existent member
        member_data = {"user_id": "00000000-0000-0000-0000-000000000000"}
        response = await authenticated_client.delete(
            f"/api/v1/teams/{team_id}/members",
            json=member_data
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_team_members(self, authenticated_client: AsyncClient, test_organization: dict, db_session):
        """Test listing team members."""
        # Create a team
        team_data = {
            "name": "List Members Team",
            "slug": "list-members-team",
            "organization_id": test_organization["id"]
        }
        create_response = await authenticated_client.post("/api/v1/teams", json=team_data)
        team_id = create_response.json()["id"]

        # Add a member
        from app.core.security import get_password_hash
        from app.models.user import User
        from app.services.organization import OrganizationService

        user = User(
            email="listmember@example.com",
            username="listmember",
            full_name="List Member",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        await OrganizationService.add_member(db_session, test_organization["id"], user.id)
        await db_session.commit()

        member_data = {"user_id": str(user.id)}
        await authenticated_client.post(f"/api/v1/teams/{team_id}/members", json=member_data)

        # List members
        response = await authenticated_client.get(f"/api/v1/teams/{team_id}/members")
        assert response.status_code == 200
        members = response.json()
        assert isinstance(members, list)

    @pytest.mark.asyncio
    async def test_team_operations_unauthorized(self, client: AsyncClient, test_organization: dict):
        """Test team operations without authentication."""
        response = await client.get("/api/v1/teams")
        assert response.status_code == 401

        team_data = {
            "name": "Unauthorized Team",
            "slug": "unauthorized-team",
            "organization_id": test_organization["id"]
        }
        response = await client.post("/api/v1/teams", json=team_data)
        assert response.status_code == 401
