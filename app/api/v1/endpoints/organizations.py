"""Organization management endpoints."""

from typing import Annotated
from uuid import UUID
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.organization import (
    OrganizationResponse,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationListResponse,
    AddMemberRequest,
    RemoveMemberRequest,
)
from app.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_in: OrganizationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrganizationResponse:
    """Create a new organization."""
    # Check if slug already exists
    existing = await OrganizationService.get_by_slug(db, org_in.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists",
        )

    org = await OrganizationService.create(db, org_in, current_user.id)
    await db.commit()
    return org


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> OrganizationListResponse:
    """List user's organizations."""
    skip = (page - 1) * page_size
    orgs, total = await OrganizationService.list_user_organizations(
        db, current_user.id, skip=skip, limit=page_size
    )

    return OrganizationListResponse(
        items=orgs,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size),
    )


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrganizationResponse:
    """Get organization by ID."""
    org = await OrganizationService.get_by_id(db, org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check if user is member
    if not await OrganizationService.is_member(db, org_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    return org


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    org_update: OrganizationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OrganizationResponse:
    """Update organization."""
    org = await OrganizationService.get_by_id(db, org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Only owner can update
    if org.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can update",
        )

    org = await OrganizationService.update(db, org, org_update)
    await db.commit()
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete organization."""
    org = await OrganizationService.get_by_id(db, org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if org.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can delete",
        )

    await OrganizationService.delete(db, org)
    await db.commit()


@router.post("/{org_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: UUID,
    member_request: AddMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    """Add member to organization."""
    org = await OrganizationService.get_by_id(db, org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if org.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can add members",
        )

    await OrganizationService.add_member(db, org_id, member_request.user_id)
    await db.commit()

    return {"message": "Member added successfully"}


@router.delete("/{org_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    org_id: UUID,
    member_request: RemoveMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove member from organization."""
    org = await OrganizationService.get_by_id(db, org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if org.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner can remove members",
        )

    await OrganizationService.remove_member(db, org_id, member_request.user_id)
    await db.commit()
