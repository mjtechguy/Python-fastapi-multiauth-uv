"""End-to-end tests for feature flag management."""


from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature_flag import FeatureFlag
from app.models.user import User
from app.services.feature_flag import FeatureFlagService


class TestFeatureFlagCreation:
    """Test feature flag creation."""

    async def test_create_feature_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test creating a new feature flag."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/v1/feature-flags",
            json={
                "name": "new_dashboard",
                "description": "New dashboard UI",
                "is_enabled": True,
                "rollout_percentage": 0.5,
            },
        )

        assert response.status_code == 201
        data = response.json()

        assert data["name"] == "new_dashboard"
        assert data["description"] == "New dashboard UI"
        assert data["is_enabled"] is True
        assert data["rollout_percentage"] == 0.5

        # Verify in database
        result = await db_session.execute(
            select(FeatureFlag).where(FeatureFlag.name == "new_dashboard")
        )
        flag = result.scalar_one_or_none()
        assert flag is not None

    async def test_create_feature_flag_requires_superuser(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that creating feature flags requires superuser."""
        response = await authenticated_client.post(
            "/api/v1/feature-flags",
            json={
                "name": "test_flag",
                "description": "Test",
                "is_enabled": False,
            },
        )

        assert response.status_code == 403

    async def test_create_duplicate_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test that duplicate flag names are rejected."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        # Create first flag
        response1 = await authenticated_client.post(
            "/api/v1/feature-flags",
            json={"name": "duplicate_test", "is_enabled": False},
        )
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await authenticated_client.post(
            "/api/v1/feature-flags",
            json={"name": "duplicate_test", "is_enabled": False},
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    async def test_create_flag_with_targeting(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test creating feature flag with targeting rules."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        targeting_rules = {
            "user_ids": [str(test_user.id)],
            "user_emails": ["special@example.com"],
        }

        response = await authenticated_client.post(
            "/api/v1/feature-flags",
            json={
                "name": "targeted_feature",
                "is_enabled": True,
                "targeting_rules": targeting_rules,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["targeting_rules"] == targeting_rules


class TestFeatureFlagListing:
    """Test listing feature flags."""

    async def test_list_feature_flags(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test listing feature flags."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        # Create some flags
        for i in range(3):
            await FeatureFlagService.create_flag(
                db_session,
                name=f"flag_{i}",
                description=f"Flag {i}",
            )

        response = await authenticated_client.get("/api/v1/feature-flags")

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert data["total"] >= 3

    async def test_list_flags_requires_superuser(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that listing requires superuser."""
        response = await authenticated_client.get("/api/v1/feature-flags")
        assert response.status_code == 403

    async def test_list_enabled_only(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test filtering enabled flags only."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        # Create enabled and disabled flags
        await FeatureFlagService.create_flag(
            db_session,
            name="enabled_flag",
            is_enabled=True,
        )
        await FeatureFlagService.create_flag(
            db_session,
            name="disabled_flag",
            is_enabled=False,
        )

        # List enabled only
        response = await authenticated_client.get(
            "/api/v1/feature-flags?enabled_only=true"
        )

        assert response.status_code == 200
        data = response.json()

        # All returned flags should be enabled
        assert all(flag["is_enabled"] for flag in data["items"])


class TestFeatureFlagRetrieval:
    """Test retrieving individual feature flags."""

    async def test_get_feature_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting specific feature flag."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        flag = await FeatureFlagService.create_flag(
            db_session,
            name="test_flag",
            description="Test flag",
        )

        response = await authenticated_client.get(
            f"/api/v1/feature-flags/{flag.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(flag.id)
        assert data["name"] == "test_flag"

    async def test_get_flag_requires_superuser(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that getting flag details requires superuser."""
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="test_flag",
        )

        response = await authenticated_client.get(
            f"/api/v1/feature-flags/{flag.id}"
        )

        assert response.status_code == 403

    async def test_get_nonexistent_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test getting non-existent flag."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.get(
            f"/api/v1/feature-flags/{fake_id}"
        )

        assert response.status_code == 404


class TestFeatureFlagUpdate:
    """Test updating feature flags."""

    async def test_update_feature_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test updating a feature flag."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        flag = await FeatureFlagService.create_flag(
            db_session,
            name="update_test",
            is_enabled=False,
        )

        response = await authenticated_client.patch(
            f"/api/v1/feature-flags/{flag.id}",
            json={
                "is_enabled": True,
                "description": "Updated description",
                "rollout_percentage": 0.25,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_enabled"] is True
        assert data["description"] == "Updated description"
        assert data["rollout_percentage"] == 0.25

    async def test_update_flag_requires_superuser(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that updating requires superuser."""
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="test_flag",
        )

        response = await authenticated_client.patch(
            f"/api/v1/feature-flags/{flag.id}",
            json={"is_enabled": True},
        )

        assert response.status_code == 403

    async def test_update_nonexistent_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test updating non-existent flag."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.patch(
            f"/api/v1/feature-flags/{fake_id}",
            json={"is_enabled": True},
        )

        assert response.status_code == 404


class TestFeatureFlagDeletion:
    """Test deleting feature flags."""

    async def test_delete_feature_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test deleting a feature flag."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        flag = await FeatureFlagService.create_flag(
            db_session,
            name="delete_test",
        )
        flag_id = flag.id

        response = await authenticated_client.delete(
            f"/api/v1/feature-flags/{flag_id}"
        )

        assert response.status_code == 204

        # Verify deleted
        result = await db_session.execute(
            select(FeatureFlag).where(FeatureFlag.id == flag_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_delete_flag_requires_superuser(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that deleting requires superuser."""
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="test_flag",
        )

        response = await authenticated_client.delete(
            f"/api/v1/feature-flags/{flag.id}"
        )

        assert response.status_code == 403


class TestFeatureFlagCheck:
    """Test checking if features are enabled."""

    async def test_check_enabled_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test checking an enabled feature flag."""
        # Create enabled flag
        await FeatureFlagService.create_flag(
            db_session,
            name="enabled_feature",
            is_enabled=True,
        )

        response = await authenticated_client.post(
            "/api/v1/feature-flags/check",
            json={"flag_name": "enabled_feature"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["flag_name"] == "enabled_feature"
        assert data["is_enabled"] is True

    async def test_check_disabled_flag(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test checking a disabled feature flag."""
        # Create disabled flag
        await FeatureFlagService.create_flag(
            db_session,
            name="disabled_feature",
            is_enabled=False,
        )

        response = await authenticated_client.post(
            "/api/v1/feature-flags/check",
            json={"flag_name": "disabled_feature"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_enabled"] is False

    async def test_check_nonexistent_flag(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test checking non-existent feature flag."""
        response = await authenticated_client.post(
            "/api/v1/feature-flags/check",
            json={"flag_name": "nonexistent"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_enabled"] is False
        assert "does not exist" in data["message"]

    async def test_check_targeted_flag(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test checking targeted feature flag."""
        # Create flag with targeting
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="targeted_feature",
            is_enabled=True,
        )

        # Add user to targeting
        targeting_rules = {"user_ids": [str(test_user.id)]}
        await FeatureFlagService.update_flag_targeting(
            db_session,
            flag,
            targeting_rules,
        )
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/v1/feature-flags/check",
            json={"flag_name": "targeted_feature"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["is_enabled"] is True


class TestFeatureFlagBulkCheck:
    """Test checking multiple feature flags."""

    async def test_check_multiple_flags(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test checking multiple flags at once."""
        # Create flags
        await FeatureFlagService.create_flag(
            db_session,
            name="feature_a",
            is_enabled=True,
        )
        await FeatureFlagService.create_flag(
            db_session,
            name="feature_b",
            is_enabled=False,
        )

        response = await authenticated_client.post(
            "/api/v1/feature-flags/check-bulk",
            json={"flag_names": ["feature_a", "feature_b", "nonexistent"]},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["flags"]["feature_a"] is True
        assert data["flags"]["feature_b"] is False
        assert data["flags"]["nonexistent"] is False


class TestFeatureFlagTargeting:
    """Test feature flag targeting functionality."""

    async def test_update_targeting_rules(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test updating targeting rules."""
        # Make user superuser
        test_user.is_superuser = True
        await db_session.commit()

        flag = await FeatureFlagService.create_flag(
            db_session,
            name="targeted_feature",
            is_enabled=True,
        )

        targeting_rules = {
            "user_ids": [str(test_user.id)],
            "user_emails": ["special@example.com"],
        }

        response = await authenticated_client.put(
            f"/api/v1/feature-flags/{flag.id}/targeting",
            json={"targeting_rules": targeting_rules},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["targeting_rules"] == targeting_rules

    async def test_targeting_by_user_id(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test targeting specific user IDs."""
        # Create flag with user targeting
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="user_targeted",
            is_enabled=True,
        )

        targeting_rules = {"user_ids": [str(test_user.id)]}
        await FeatureFlagService.update_flag_targeting(
            db_session,
            flag,
            targeting_rules,
        )
        await db_session.commit()

        # Check if enabled for this user
        is_enabled = await FeatureFlagService.check_user_access(
            db_session,
            "user_targeted",
            test_user.id,
            test_user.email,
        )

        assert is_enabled is True

    async def test_targeting_by_email(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        db_session: AsyncSession,
    ):
        """Test targeting specific emails."""
        # Create flag with email targeting
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="email_targeted",
            is_enabled=True,
        )

        targeting_rules = {"user_emails": [test_user.email]}
        await FeatureFlagService.update_flag_targeting(
            db_session,
            flag,
            targeting_rules,
        )
        await db_session.commit()

        # Check if enabled for this user
        is_enabled = await FeatureFlagService.check_user_access(
            db_session,
            "email_targeted",
            test_user.id,
            test_user.email,
        )

        assert is_enabled is True


class TestFeatureFlagRollout:
    """Test feature flag rollout percentage."""

    async def test_rollout_percentage(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test rollout percentage functionality."""
        # Create flag with 50% rollout
        flag = await FeatureFlagService.create_flag(
            db_session,
            name="rollout_feature",
            is_enabled=True,
        )

        await FeatureFlagService.update_flag(
            db_session,
            flag,
            rollout_percentage=0.5,
        )
        await db_session.commit()

        # Test with multiple users
        enabled_count = 0
        total_users = 100

        for i in range(total_users):
            from uuid import uuid4

            test_id = uuid4()
            is_enabled = flag.is_enabled_for_user(test_id, f"user{i}@example.com")
            if is_enabled:
                enabled_count += 1

        # Should be roughly 50% (allow 20% variance for small sample)
        assert 30 <= enabled_count <= 70


class TestFeatureFlagAuthorization:
    """Test feature flag authorization."""

    async def test_check_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Test that checking flags requires authentication."""
        response = await client.post(
            "/api/v1/feature-flags/check",
            json={"flag_name": "test"},
        )

        assert response.status_code == 401

    async def test_non_superuser_can_check_flags(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that non-superusers can check flags."""
        # Create flag
        await FeatureFlagService.create_flag(
            db_session,
            name="public_check",
            is_enabled=True,
        )

        # Regular user can check
        response = await authenticated_client.post(
            "/api/v1/feature-flags/check",
            json={"flag_name": "public_check"},
        )

        assert response.status_code == 200

    async def test_only_superuser_can_manage_flags(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that only superusers can manage flags."""
        # Try to create (should fail)
        response = await authenticated_client.post(
            "/api/v1/feature-flags",
            json={"name": "test", "is_enabled": False},
        )
        assert response.status_code == 403

        # Try to list (should fail)
        response = await authenticated_client.get("/api/v1/feature-flags")
        assert response.status_code == 403
