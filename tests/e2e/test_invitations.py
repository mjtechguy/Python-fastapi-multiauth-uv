"""End-to-end tests for invitation management."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.user import User
from app.services.invitation_service import InvitationService
from app.services.organization import OrganizationService
from app.services.user import UserService


class TestInvitationCreation:
    """Test invitation creation."""

    async def test_create_invitation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test creating a new invitation."""
        invitee_email = f"invitee_{datetime.utcnow().timestamp()}@example.com"

        response = await authenticated_client.post(
            f"/api/v1/invitations/organizations/{test_organization.id}",
            json={"email": invitee_email, "expires_in_days": 7},
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response contains all fields
        assert "id" in data
        assert "token" in data  # Token is shown on creation
        assert data["email"] == invitee_email
        assert data["organization_id"] == str(test_organization.id)
        assert data["inviter_id"] == str(test_user.id)
        assert data["is_accepted"] is False
        assert "expires_at" in data
        assert "created_at" in data

        # Verify invitation was created in database
        result = await db_session.execute(
            select(Invitation).where(Invitation.email == invitee_email)
        )
        invitation = result.scalar_one_or_none()
        assert invitation is not None
        assert invitation.organization_id == test_organization.id

    async def test_create_invitation_with_custom_expiry(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
    ):
        """Test creating invitation with custom expiration."""
        invitee_email = f"invitee_{datetime.utcnow().timestamp()}@example.com"

        response = await authenticated_client.post(
            f"/api/v1/invitations/organizations/{test_organization.id}",
            json={"email": invitee_email, "expires_in_days": 14},
        )

        assert response.status_code == 201
        data = response.json()

        expires_at = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))

        # Should be approximately 14 days
        delta = expires_at - created_at
        assert 13 < delta.days <= 14

    async def test_create_invitation_requires_auth(
        self,
        client: AsyncClient,
        test_organization: Organization,
    ):
        """Test that creating invitations requires authentication."""
        response = await client.post(
            f"/api/v1/invitations/organizations/{test_organization.id}",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 401

    async def test_create_invitation_requires_membership(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that only organization members can send invitations."""
        # Create another organization
        from app.services.user import UserService

        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        other_org_data = {
            "name": "Other Org",
            "slug": f"other-org-{datetime.utcnow().timestamp()}",
        }
        from app.schemas.organization import OrganizationCreate

        other_org = await OrganizationService.create(
            db_session,
            OrganizationCreate(**other_org_data),
            owner_id=other_user.id,
        )

        # Try to invite to other org
        response = await authenticated_client.post(
            f"/api/v1/invitations/organizations/{other_org.id}",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 400
        assert "Only organization members" in response.json()["detail"]

    async def test_create_invitation_duplicate_pending(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test that duplicate pending invitations are rejected."""
        invitee_email = f"invitee_{datetime.utcnow().timestamp()}@example.com"

        # Create first invitation
        response1 = await authenticated_client.post(
            f"/api/v1/invitations/organizations/{test_organization.id}",
            json={"email": invitee_email},
        )
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await authenticated_client.post(
            f"/api/v1/invitations/organizations/{test_organization.id}",
            json={"email": invitee_email},
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]

    async def test_create_invitation_for_existing_member(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
        test_user: User,
    ):
        """Test that inviting existing members is rejected."""
        response = await authenticated_client.post(
            f"/api/v1/invitations/organizations/{test_organization.id}",
            json={"email": test_user.email},
        )

        assert response.status_code == 400
        assert "already a member" in response.json()["detail"]


class TestInvitationListing:
    """Test listing invitations."""

    async def test_list_organization_invitations(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test listing organization invitations."""
        # Create some invitations
        await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"user1_{datetime.utcnow().timestamp()}@example.com",
        )
        await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"user2_{datetime.utcnow().timestamp()}@example.com",
        )

        response = await authenticated_client.get(
            f"/api/v1/invitations/organizations/{test_organization.id}"
        )

        assert response.status_code == 200
        data = response.json()

        assert "items" in data
        assert "total" in data
        assert data["total"] >= 2
        assert len(data["items"]) >= 2

        # Verify invitation structure
        for invitation in data["items"]:
            assert "id" in invitation
            assert "email" in invitation
            assert "organization_id" in invitation
            assert "token" not in invitation  # Token not shown in list

    async def test_list_organization_invitations_with_filters(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test listing invitations with expired/accepted filters."""
        # Create active invitation
        await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"active_{datetime.utcnow().timestamp()}@example.com",
        )

        # Create expired invitation
        expired_inv = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"expired_{datetime.utcnow().timestamp()}@example.com",
        )
        expired_inv.expires_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.commit()

        # List without expired
        response = await authenticated_client.get(
            f"/api/v1/invitations/organizations/{test_organization.id}"
        )
        assert response.status_code == 200
        active_only = response.json()

        # List with expired
        response = await authenticated_client.get(
            f"/api/v1/invitations/organizations/{test_organization.id}?include_expired=true"
        )
        assert response.status_code == 200
        with_expired = response.json()

        assert with_expired["total"] > active_only["total"]

    async def test_list_invitations_requires_membership(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that only members can list organization invitations."""
        # Create another organization with different owner
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        from app.schemas.organization import OrganizationCreate

        other_org = await OrganizationService.create(
            db_session,
            OrganizationCreate(
                name="Other Org",
                slug=f"other-org-{datetime.utcnow().timestamp()}",
            ),
            owner_id=other_user.id,
        )

        # Try to list invitations
        response = await authenticated_client.get(
            f"/api/v1/invitations/organizations/{other_org.id}"
        )

        assert response.status_code == 403

    async def test_list_my_invitations(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test listing invitations for current user."""
        # Create another user to send invitation
        other_user = await UserService.create_user(
            db_session,
            email=f"inviter_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Inviter User",
        )

        # Add other user to organization
        await OrganizationService.add_member(db_session, test_organization.id, other_user.id)

        # Create invitation to test_user
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            other_user.id,
            test_user.email,
        )

        # List invitations for test_user
        response = await authenticated_client.get("/api/v1/invitations/me")

        assert response.status_code == 200
        data = response.json()

        assert data["total"] >= 1
        found = any(inv["id"] == str(invitation.id) for inv in data["items"])
        assert found


class TestInvitationRetrieval:
    """Test retrieving individual invitations."""

    async def test_get_invitation_by_id(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test getting specific invitation by ID."""
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"test_{datetime.utcnow().timestamp()}@example.com",
        )

        response = await authenticated_client.get(
            f"/api/v1/invitations/{invitation.id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invitation.id)
        assert data["email"] == invitation.email
        assert "organization_name" in data
        assert "inviter_email" in data

    async def test_get_nonexistent_invitation(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test getting non-existent invitation."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.get(f"/api/v1/invitations/{fake_id}")

        assert response.status_code == 404

    async def test_cannot_get_unauthorized_invitation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that users cannot access unauthorized invitations."""
        # Create another org and invitation
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        from app.schemas.organization import OrganizationCreate

        other_org = await OrganizationService.create(
            db_session,
            OrganizationCreate(
                name="Other Org",
                slug=f"other-org-{datetime.utcnow().timestamp()}",
            ),
            owner_id=other_user.id,
        )

        invitation = await InvitationService.create_invitation(
            db_session,
            other_org.id,
            other_user.id,
            f"someone_{datetime.utcnow().timestamp()}@example.com",
        )

        # Try to access invitation
        response = await authenticated_client.get(
            f"/api/v1/invitations/{invitation.id}"
        )

        assert response.status_code == 403


class TestInvitationAcceptance:
    """Test accepting invitations."""

    async def test_accept_invitation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test accepting an invitation."""
        # Create invitation for test_user
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_organization.owner_id,
            test_user.email,
        )

        response = await authenticated_client.post(
            "/api/v1/invitations/accept",
            json={"token": invitation.token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["organization_id"] == str(test_organization.id)

        # Verify user is now a member
        is_member = await OrganizationService.is_member(
            db_session, test_organization.id, test_user.id
        )
        assert is_member

        # Verify invitation is marked as accepted
        await db_session.refresh(invitation)
        assert invitation.is_accepted is True
        assert invitation.accepted_by_id == test_user.id

    async def test_accept_invitation_with_wrong_email(
        self,
        authenticated_client: AsyncClient,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test that invitation email must match user email."""
        # Create invitation for different email
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_organization.owner_id,
            f"different_{datetime.utcnow().timestamp()}@example.com",
        )

        response = await authenticated_client.post(
            "/api/v1/invitations/accept",
            json={"token": invitation.token},
        )

        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    async def test_accept_expired_invitation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test that expired invitations cannot be accepted."""
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_organization.owner_id,
            test_user.email,
        )

        # Expire the invitation
        invitation.expires_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.commit()

        response = await authenticated_client.post(
            "/api/v1/invitations/accept",
            json={"token": invitation.token},
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"]

    async def test_accept_already_accepted_invitation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test that already accepted invitations cannot be re-accepted."""
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_organization.owner_id,
            test_user.email,
        )

        # Accept once
        await InvitationService.accept_invitation(
            db_session, invitation.token, test_user.id
        )

        # Try to accept again
        response = await authenticated_client.post(
            "/api/v1/invitations/accept",
            json={"token": invitation.token},
        )

        assert response.status_code == 400
        assert "already been accepted" in response.json()["detail"]


class TestInvitationCancellation:
    """Test cancelling invitations."""

    async def test_cancel_invitation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test cancelling an invitation."""
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"cancel_{datetime.utcnow().timestamp()}@example.com",
        )
        invitation_id = invitation.id

        response = await authenticated_client.delete(
            f"/api/v1/invitations/{invitation_id}"
        )

        assert response.status_code == 204

        # Verify invitation is deleted
        result = await db_session.execute(
            select(Invitation).where(Invitation.id == invitation_id)
        )
        assert result.scalar_one_or_none() is None

    async def test_cancel_nonexistent_invitation(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test cancelling non-existent invitation."""
        from uuid import uuid4

        fake_id = uuid4()
        response = await authenticated_client.delete(
            f"/api/v1/invitations/{fake_id}"
        )

        assert response.status_code == 404

    async def test_cannot_cancel_unauthorized_invitation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that users cannot cancel unauthorized invitations."""
        # Create another org and invitation
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        from app.schemas.organization import OrganizationCreate

        other_org = await OrganizationService.create(
            db_session,
            OrganizationCreate(
                name="Other Org",
                slug=f"other-org-{datetime.utcnow().timestamp()}",
            ),
            owner_id=other_user.id,
        )

        invitation = await InvitationService.create_invitation(
            db_session,
            other_org.id,
            other_user.id,
            f"someone_{datetime.utcnow().timestamp()}@example.com",
        )

        response = await authenticated_client.delete(
            f"/api/v1/invitations/{invitation.id}"
        )

        assert response.status_code == 403


class TestInvitationResend:
    """Test resending invitations."""

    async def test_resend_invitation(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test resending an invitation."""
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            f"resend_{datetime.utcnow().timestamp()}@example.com",
        )
        original_token = invitation.token

        response = await authenticated_client.post(
            f"/api/v1/invitations/{invitation.id}/resend"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify new token is different
        assert data["token"] != original_token

        # Verify expiration is extended
        await db_session.refresh(invitation)
        assert invitation.expires_at > datetime.now(UTC)

    async def test_resend_accepted_invitation_fails(
        self,
        authenticated_client: AsyncClient,
        test_user: User,
        test_organization: Organization,
        db_session: AsyncSession,
    ):
        """Test that accepted invitations cannot be resent."""
        invitation = await InvitationService.create_invitation(
            db_session,
            test_organization.id,
            test_user.id,
            test_user.email,
        )

        # Accept invitation
        await InvitationService.accept_invitation(
            db_session, invitation.token, test_user.id
        )

        # Try to resend
        response = await authenticated_client.post(
            f"/api/v1/invitations/{invitation.id}/resend"
        )

        assert response.status_code == 400
        assert "accepted" in response.json()["detail"]

    async def test_resend_unauthorized_invitation(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test that only inviter/owner can resend invitations."""
        # Create another org and invitation
        other_user = await UserService.create_user(
            db_session,
            email=f"other_{datetime.utcnow().timestamp()}@example.com",
            password="TestPassword123!",
            full_name="Other User",
        )

        from app.schemas.organization import OrganizationCreate

        other_org = await OrganizationService.create(
            db_session,
            OrganizationCreate(
                name="Other Org",
                slug=f"other-org-{datetime.utcnow().timestamp()}",
            ),
            owner_id=other_user.id,
        )

        invitation = await InvitationService.create_invitation(
            db_session,
            other_org.id,
            other_user.id,
            f"someone_{datetime.utcnow().timestamp()}@example.com",
        )

        response = await authenticated_client.post(
            f"/api/v1/invitations/{invitation.id}/resend"
        )

        assert response.status_code == 400
        assert "authorized" in response.json()["detail"]
