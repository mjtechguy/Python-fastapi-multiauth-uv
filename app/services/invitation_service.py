"""Invitation service for organization member invitations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.invitation import Invitation
from app.models.organization import Organization
from app.models.user import User
from app.services.organization import OrganizationService


class InvitationService:
    """Service for managing organization invitations."""

    DEFAULT_EXPIRY_DAYS = 7

    @staticmethod
    async def create_invitation(
        db: AsyncSession,
        organization_id: UUID,
        inviter_id: UUID,
        email: str,
        expires_in_days: int = DEFAULT_EXPIRY_DAYS,
    ) -> Invitation:
        """Create a new invitation to join an organization.

        Args:
            db: Database session
            organization_id: ID of the organization
            inviter_id: ID of the user sending the invitation
            email: Email address to invite
            expires_in_days: Days until invitation expires (default: 7)

        Returns:
            Created invitation

        Raises:
            ValueError: If organization doesn't exist, inviter is not a member,
                       or email already has pending invitation
        """
        # Verify organization exists
        org_result = await db.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        organization = org_result.scalar_one_or_none()
        if not organization:
            raise ValueError("Organization not found")

        # Verify inviter is a member or owner
        is_owner = organization.owner_id == inviter_id
        is_member = await OrganizationService.is_member(db, organization_id, inviter_id)

        if not (is_owner or is_member):
            raise ValueError("Only organization members can send invitations")

        # Check for existing user with this email
        existing_user_result = await db.execute(
            select(User).where(User.email == email.lower())
        )
        existing_user = existing_user_result.scalar_one_or_none()

        # If user exists, check if already a member
        if existing_user:
            is_already_member = await OrganizationService.is_member(
                db, organization_id, existing_user.id
            )
            if is_already_member:
                raise ValueError("User is already a member of this organization")

        # Check for existing pending invitation
        existing_invitation = await InvitationService.get_pending_invitation(
            db, organization_id, email
        )
        if existing_invitation:
            raise ValueError(
                "An active invitation for this email already exists. "
                "Cancel or wait for it to expire before sending a new one."
            )

        # Generate token and hash it
        from datetime import timedelta

        from app.core.encryption import EncryptionService

        plaintext_token = Invitation.generate_token()
        token_hash = EncryptionService.hash_token(plaintext_token)

        # Create invitation with hashed token
        invitation = Invitation(
            organization_id=organization_id,
            inviter_id=inviter_id,
            email=email.lower(),
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
        )

        db.add(invitation)
        await db.flush()
        await db.refresh(invitation)

        # Store plaintext token temporarily so endpoint can return it
        # This is safe because it's only in memory and returned once
        invitation.plaintext_token = plaintext_token  # type: ignore

        return invitation

    @staticmethod
    async def get_invitation_by_id(
        db: AsyncSession, invitation_id: UUID
    ) -> Invitation | None:
        """Get invitation by ID."""
        result = await db.execute(
            select(Invitation)
            .options(
                selectinload(Invitation.organization),
                selectinload(Invitation.inviter),
            )
            .where(Invitation.id == invitation_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_invitation_by_token(db: AsyncSession, token: str) -> Invitation | None:
        """Get invitation by token (hashes token for lookup)."""
        from app.core.encryption import EncryptionService

        token_hash = EncryptionService.hash_token(token)
        result = await db.execute(
            select(Invitation)
            .options(
                selectinload(Invitation.organization),
                selectinload(Invitation.inviter),
            )
            .where(Invitation.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_pending_invitation(
        db: AsyncSession, organization_id: UUID, email: str
    ) -> Invitation | None:
        """Get pending (non-accepted, non-expired) invitation for email in organization."""
        now = datetime.now(UTC)
        result = await db.execute(
            select(Invitation).where(
                and_(
                    Invitation.organization_id == organization_id,
                    Invitation.email == email.lower(),
                    Invitation.is_accepted is False,
                    Invitation.expires_at > now,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_organization_invitations(
        db: AsyncSession,
        organization_id: UUID,
        include_expired: bool = False,
        include_accepted: bool = False,
    ) -> list[Invitation]:
        """List all invitations for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            include_expired: Include expired invitations (default: False)
            include_accepted: Include accepted invitations (default: False)

        Returns:
            List of invitations
        """
        conditions = [Invitation.organization_id == organization_id]

        if not include_accepted:
            conditions.append(Invitation.is_accepted is False)

        if not include_expired:
            conditions.append(Invitation.expires_at > datetime.now(UTC))

        result = await db.execute(
            select(Invitation)
            .options(
                selectinload(Invitation.inviter),
                selectinload(Invitation.accepted_by),
            )
            .where(and_(*conditions))
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_user_invitations(db: AsyncSession, email: str) -> list[Invitation]:
        """List all pending invitations for a user's email.

        Args:
            db: Database session
            email: User's email address

        Returns:
            List of pending invitations
        """
        now = datetime.now(UTC)
        result = await db.execute(
            select(Invitation)
            .options(
                selectinload(Invitation.organization),
                selectinload(Invitation.inviter),
            )
            .where(
                and_(
                    Invitation.email == email.lower(),
                    Invitation.is_accepted is False,
                    Invitation.expires_at > now,
                )
            )
            .order_by(Invitation.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def accept_invitation(
        db: AsyncSession, token: str, user_id: UUID
    ) -> Invitation:
        """Accept an invitation and add user to organization.

        Args:
            db: Database session
            token: Invitation token
            user_id: ID of user accepting the invitation

        Returns:
            Accepted invitation

        Raises:
            ValueError: If invitation not found, invalid, expired, or already accepted
        """
        invitation = await InvitationService.get_invitation_by_token(db, token)

        if not invitation:
            raise ValueError("Invitation not found")

        if not invitation.is_valid():
            if invitation.is_accepted:
                raise ValueError("Invitation has already been accepted")
            raise ValueError("Invitation has expired")

        # Get user to verify email matches
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        if user.email.lower() != invitation.email.lower():
            raise ValueError("Invitation email does not match your account email")

        # Add user to organization
        try:
            await OrganizationService.add_member(
                db, invitation.organization_id, user_id
            )
        except ValueError as e:
            # Handle case where user is already in another org
            raise ValueError(f"Failed to add user to organization: {e!s}") from e

        # Mark invitation as accepted
        invitation.is_accepted = True
        invitation.accepted_at = datetime.now(UTC)
        invitation.accepted_by_id = user_id

        await db.flush()
        await db.refresh(invitation)

        return invitation

    @staticmethod
    async def cancel_invitation(
        db: AsyncSession, invitation_id: UUID, user_id: UUID
    ) -> bool:
        """Cancel (delete) an invitation.

        Args:
            db: Database session
            invitation_id: ID of invitation to cancel
            user_id: ID of user requesting cancellation

        Returns:
            True if cancelled, False if not found

        Raises:
            ValueError: If user is not authorized to cancel
        """
        invitation = await InvitationService.get_invitation_by_id(db, invitation_id)

        if not invitation:
            return False

        # Only inviter, org owner, or the invited user can cancel
        org_result = await db.execute(
            select(Organization).where(Organization.id == invitation.organization_id)
        )
        organization = org_result.scalar_one_or_none()

        # Get user's email
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        is_inviter = invitation.inviter_id == user_id
        is_owner = organization and organization.owner_id == user_id
        is_invitee = user and user.email.lower() == invitation.email.lower()

        if not (is_inviter or is_owner or is_invitee):
            raise ValueError("Not authorized to cancel this invitation")

        await db.delete(invitation)
        await db.flush()

        return True

    @staticmethod
    async def resend_invitation(
        db: AsyncSession, invitation_id: UUID, user_id: UUID, expires_in_days: int = DEFAULT_EXPIRY_DAYS
    ) -> Invitation:
        """Resend an invitation by creating a new token and extending expiration.

        Args:
            db: Database session
            invitation_id: ID of invitation to resend
            user_id: ID of user requesting resend
            expires_in_days: Days until new expiration (default: 7)

        Returns:
            Updated invitation

        Raises:
            ValueError: If invitation not found, already accepted, or user not authorized
        """
        invitation = await InvitationService.get_invitation_by_id(db, invitation_id)

        if not invitation:
            raise ValueError("Invitation not found")

        if invitation.is_accepted:
            raise ValueError("Cannot resend an accepted invitation")

        # Verify user is inviter or org owner
        org_result = await db.execute(
            select(Organization).where(Organization.id == invitation.organization_id)
        )
        organization = org_result.scalar_one_or_none()

        is_inviter = invitation.inviter_id == user_id
        is_owner = organization and organization.owner_id == user_id

        if not (is_inviter or is_owner):
            raise ValueError("Not authorized to resend this invitation")

        # Generate new token and extend expiration
        invitation.token = Invitation.generate_token()
        invitation.expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        await db.flush()
        await db.refresh(invitation)

        return invitation

    @staticmethod
    async def cleanup_expired_invitations(db: AsyncSession) -> int:
        """Delete all expired invitations.

        Args:
            db: Database session

        Returns:
            Number of invitations deleted
        """
        now = datetime.now(UTC)

        # Get expired invitations
        result = await db.execute(
            select(Invitation).where(
                and_(
                    Invitation.is_accepted is False,
                    Invitation.expires_at <= now,
                )
            )
        )
        expired_invitations = result.scalars().all()

        count = len(expired_invitations)

        for invitation in expired_invitations:
            await db.delete(invitation)

        await db.flush()

        return count
