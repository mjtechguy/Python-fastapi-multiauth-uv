"""E2E tests for user management endpoints."""

import pytest
from httpx import AsyncClient


class TestUserProfile:
    """Test user profile endpoints."""

    @pytest.mark.asyncio
    async def test_get_me(self, authenticated_client: AsyncClient, test_user: dict):
        """Test getting current user profile."""
        response = await authenticated_client.get("/api/v1/users/me")
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["email"] == test_user["email"]
        assert user_data["full_name"] == test_user["full_name"]
        assert "id" in user_data
        assert "hashed_password" not in user_data

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client: AsyncClient):
        """Test getting profile without authentication."""
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_me(self, authenticated_client: AsyncClient, test_user: dict):
        """Test updating current user profile."""
        update_data = {
            "full_name": "Updated Test User",
            "bio": "This is my updated bio"
        }

        response = await authenticated_client.put("/api/v1/users/me", json=update_data)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["full_name"] == update_data["full_name"]

    @pytest.mark.asyncio
    async def test_update_me_partial(self, authenticated_client: AsyncClient):
        """Test partial profile update."""
        update_data = {
            "full_name": "Partially Updated Name"
        }

        response = await authenticated_client.put("/api/v1/users/me", json=update_data)
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["full_name"] == update_data["full_name"]


class TestPasswordUpdate:
    """Test password update functionality."""

    @pytest.mark.asyncio
    async def test_update_password(self, authenticated_client: AsyncClient, test_user: dict):
        """Test updating user password."""
        password_data = {
            "current_password": test_user["password"],
            "new_password": "NewSecurePassword123!"
        }

        response = await authenticated_client.put("/api/v1/users/me/password", json=password_data)
        assert response.status_code == 200

        # Verify can login with new password
        login_response = await authenticated_client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user["email"],
                "password": password_data["new_password"]
            }
        )
        assert login_response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_password_wrong_current(self, authenticated_client: AsyncClient):
        """Test password update with wrong current password."""
        password_data = {
            "current_password": "WrongPassword123!",
            "new_password": "NewSecurePassword123!"
        }

        response = await authenticated_client.put("/api/v1/users/me/password", json=password_data)
        assert response.status_code == 400
        assert "password" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_password_weak_new_password(self, authenticated_client: AsyncClient, test_user: dict):
        """Test password update with weak new password."""
        password_data = {
            "current_password": test_user["password"],
            "new_password": "weak"
        }

        response = await authenticated_client.put("/api/v1/users/me/password", json=password_data)
        # Should fail validation (422) or business logic (400)
        assert response.status_code in [400, 422]


class TestUserList:
    """Test user listing (superuser only)."""

    @pytest.mark.asyncio
    async def test_list_users_as_superuser(self, client: AsyncClient, db_session):
        """Test listing users as superuser."""
        # Create superuser
        from app.core.security import create_access_token, get_password_hash
        from app.models.user import User

        superuser = User(
            email="superadmin@example.com",
            username="superadmin",
            full_name="Super Admin",
            hashed_password=get_password_hash("SuperPassword123!"),
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        db_session.add(superuser)
        await db_session.commit()
        await db_session.refresh(superuser)

        # Get token and make authenticated request
        token = create_access_token(str(superuser.id))
        client.headers.update({"Authorization": f"Bearer {token}"})

        response = await client.get("/api/v1/users")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_users_as_regular_user(self, authenticated_client: AsyncClient):
        """Test listing users as regular user (should fail)."""
        response = await authenticated_client.get("/api/v1/users")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_pagination(self, client: AsyncClient, db_session):
        """Test user list pagination."""
        # Create superuser
        from app.core.security import create_access_token, get_password_hash
        from app.models.user import User

        superuser = User(
            email="paginated_admin@example.com",
            username="paginated_admin",
            full_name="Paginated Admin",
            hashed_password=get_password_hash("SuperPassword123!"),
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        db_session.add(superuser)
        await db_session.commit()
        await db_session.refresh(superuser)

        token = create_access_token(str(superuser.id))
        client.headers.update({"Authorization": f"Bearer {token}"})

        # Test pagination
        response = await client.get("/api/v1/users?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10


class TestGetUser:
    """Test getting specific user by ID."""

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, authenticated_client: AsyncClient, test_user: dict):
        """Test getting user by ID."""
        response = await authenticated_client.get(f"/api/v1/users/{test_user['id']}")
        assert response.status_code == 200
        user_data = response.json()
        assert user_data["id"] == test_user["id"]
        assert user_data["email"] == test_user["email"]

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, authenticated_client: AsyncClient):
        """Test getting non-existent user."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await authenticated_client.get(f"/api/v1/users/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_user_invalid_uuid(self, authenticated_client: AsyncClient):
        """Test getting user with invalid UUID."""
        response = await authenticated_client.get("/api/v1/users/not-a-uuid")
        assert response.status_code == 422


class TestDeleteUser:
    """Test user deletion (superuser only)."""

    @pytest.mark.asyncio
    async def test_delete_user_as_superuser(self, client: AsyncClient, db_session):
        """Test deleting user as superuser."""
        # Create superuser and target user
        from app.core.security import create_access_token, get_password_hash
        from app.models.user import User

        superuser = User(
            email="delete_admin@example.com",
            username="delete_admin",
            full_name="Delete Admin",
            hashed_password=get_password_hash("SuperPassword123!"),
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        db_session.add(superuser)

        target_user = User(
            email="to_delete@example.com",
            username="to_delete",
            full_name="To Delete",
            hashed_password=get_password_hash("Password123!"),
            is_active=True,
            is_verified=True,
        )
        db_session.add(target_user)
        await db_session.commit()
        await db_session.refresh(superuser)
        await db_session.refresh(target_user)

        # Authenticate as superuser
        token = create_access_token(str(superuser.id))
        client.headers.update({"Authorization": f"Bearer {token}"})

        # Delete target user
        response = await client.delete(f"/api/v1/users/{target_user.id}")
        assert response.status_code == 204

        # Verify user is deleted
        get_response = await client.get(f"/api/v1/users/{target_user.id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_as_regular_user(self, authenticated_client: AsyncClient, test_user: dict):
        """Test deleting user as regular user (should fail)."""
        response = await authenticated_client.delete(f"/api/v1/users/{test_user['id']}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user(self, client: AsyncClient, db_session):
        """Test deleting non-existent user."""
        # Create superuser
        from app.core.security import create_access_token, get_password_hash
        from app.models.user import User

        superuser = User(
            email="delete_notfound_admin@example.com",
            username="delete_notfound_admin",
            full_name="Delete NotFound Admin",
            hashed_password=get_password_hash("SuperPassword123!"),
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        db_session.add(superuser)
        await db_session.commit()
        await db_session.refresh(superuser)

        token = create_access_token(str(superuser.id))
        client.headers.update({"Authorization": f"Bearer {token}"})

        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(f"/api/v1/users/{fake_id}")
        assert response.status_code == 404
