"""Invitation management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.invitation import (
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreate,
    InvitationCreateResponse,
    InvitationDetailResponse,
    InvitationListResponse,
    InvitationResponse,
)
from app.services.invitation_service import InvitationService
from app.services.organization import OrganizationService

router = APIRouter(prefix="/invitations", tags=["invitations"])


@router.post(
    "/organizations/{organization_id}",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    organization_id: UUID,
    data: InvitationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InvitationCreateResponse:
    """
    Create an invitation to join an organization.

    Only organization owners and members can send invitations.
    The invited user will receive an email with the invitation token.

    **Note:** Implement email sending in production to automatically notify invitees.
    """
    try:
        invitation = await InvitationService.create_invitation(
            db=db,
            organization_id=organization_id,
            inviter_id=current_user.id,
            email=data.email,
            expires_in_days=data.expires_in_days,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return InvitationCreateResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        inviter_id=invitation.inviter_id,
        email=invitation.email,
        is_accepted=invitation.is_accepted,
        accepted_at=invitation.accepted_at,
        accepted_by_id=invitation.accepted_by_id,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        token=getattr(invitation, "plaintext_token", None),  # Plaintext token returned once
    )


@router.get(
    "/organizations/{organization_id}",
    response_model=InvitationListResponse,
)
async def list_organization_invitations(
    organization_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_expired: bool = False,
    include_accepted: bool = False,
) -> InvitationListResponse:
    """
    List all invitations for an organization.

    Only organization owners and members can view invitations.

    Query Parameters:
        include_expired: Include expired invitations (default: false)
        include_accepted: Include accepted invitations (default: false)
    """
    # Verify user is organization member or owner
    organization = await OrganizationService.get_by_id(db, organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    is_owner = organization.owner_id == current_user.id
    is_member = await OrganizationService.is_member(db, organization_id, current_user.id)

    if not (is_owner or is_member or current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view organization invitations",
        )

    invitations = await InvitationService.list_organization_invitations(
        db=db,
        organization_id=organization_id,
        include_expired=include_expired,
        include_accepted=include_accepted,
    )

    return InvitationListResponse(
        items=[InvitationResponse.model_validate(inv) for inv in invitations],
        total=len(invitations),
        page=1,
        page_size=len(invitations),
        pages=1,
    )


@router.get(
    "/me",
    response_model=InvitationListResponse,
)
async def list_my_invitations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InvitationListResponse:
    """
    List all pending invitations for the current user.

    Returns invitations sent to the user's email address that have not been accepted or expired.
    """
    invitations = await InvitationService.list_user_invitations(
        db=db,
        email=current_user.email,
    )

    # Enrich with organization details
    items = []
    for inv in invitations:
        response_data = InvitationResponse.model_validate(inv)
        items.append(response_data)

    return InvitationListResponse(
        items=items,
        total=len(items),
        page=1,
        page_size=len(items),
        pages=1,
    )


@router.get(
    "/{invitation_id}",
    response_model=InvitationDetailResponse,
)
async def get_invitation(
    invitation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InvitationDetailResponse:
    """
    Get details of a specific invitation.

    Only the inviter, organization owner, or invitee can view invitation details.
    """
    invitation = await InvitationService.get_invitation_by_id(db, invitation_id)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )

    # Check authorization
    organization = await OrganizationService.get_by_id(db, invitation.organization_id)
    is_inviter = invitation.inviter_id == current_user.id
    is_owner = organization and organization.owner_id == current_user.id
    is_invitee = current_user.email.lower() == invitation.email.lower()

    if not (is_inviter or is_owner or is_invitee or current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this invitation",
        )

    return InvitationDetailResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        inviter_id=invitation.inviter_id,
        email=invitation.email,
        is_accepted=invitation.is_accepted,
        accepted_at=invitation.accepted_at,
        accepted_by_id=invitation.accepted_by_id,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        organization_name=invitation.organization.name if invitation.organization else None,
        inviter_email=invitation.inviter.email if invitation.inviter else None,
        inviter_name=invitation.inviter.full_name if invitation.inviter else None,
    )


@router.post(
    "/accept",
    response_model=InvitationAcceptResponse,
)
async def accept_invitation(
    data: InvitationAcceptRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InvitationAcceptResponse:
    """
    Accept an invitation and join the organization.

    The invitation token must match an email, and the user's email must match
    the invitation's email address.
    """
    try:
        invitation = await InvitationService.accept_invitation(
            db=db,
            token=data.token,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    # Get organization details
    organization = await OrganizationService.get_by_id(db, invitation.organization_id)

    return InvitationAcceptResponse(
        message=f"Successfully joined {organization.name if organization else 'organization'}",
        organization_id=invitation.organization_id,
        organization_name=organization.name if organization else "Unknown",
    )


@router.delete(
    "/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_invitation(
    invitation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Cancel an invitation.

    Only the inviter, organization owner, or invitee can cancel an invitation.
    """
    try:
        success = await InvitationService.cancel_invitation(
            db=db,
            invitation_id=invitation_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )


@router.post(
    "/{invitation_id}/resend",
    response_model=InvitationCreateResponse,
)
async def resend_invitation(
    invitation_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InvitationCreateResponse:
    """
    Resend an invitation by generating a new token and extending expiration.

    Only the inviter or organization owner can resend invitations.

    **Note:** Implement email sending in production to automatically notify invitees.
    """
    try:
        invitation = await InvitationService.resend_invitation(
            db=db,
            invitation_id=invitation_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return InvitationCreateResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        inviter_id=invitation.inviter_id,
        email=invitation.email,
        is_accepted=invitation.is_accepted,
        accepted_at=invitation.accepted_at,
        accepted_by_id=invitation.accepted_by_id,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        token=getattr(invitation, "plaintext_token", None),  # Plaintext token returned once
    )
