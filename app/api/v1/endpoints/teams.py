"""Team management endpoints."""

from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.team import (
    AddTeamMemberRequest,
    RemoveTeamMemberRequest,
    TeamCreate,
    TeamListResponse,
    TeamResponse,
    TeamUpdate,
    TeamWithMembers,
)
from app.schemas.user import UserResponse
from app.services.organization import OrganizationService
from app.services.team import TeamService
from app.services.user import UserService

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    team_in: TeamCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamResponse:
    """
    Create a new team within an organization.

    User must be a member of the organization to create a team.
    """
    # Check if user is member of the organization
    is_member = await OrganizationService.is_member(
        db, team_in.organization_id, current_user.id
    )
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    # Check if organization exists
    org = await OrganizationService.get_by_id(db, team_in.organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check if team slug is unique within organization
    existing_team = await TeamService.get_by_slug(
        db, team_in.slug, team_in.organization_id
    )
    if existing_team:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team with this slug already exists in this organization",
        )

    team = await TeamService.create(db, team_in, current_user.id)
    await db.commit()
    await db.refresh(team)

    return team


@router.get("", response_model=TeamListResponse)
async def list_teams(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    organization_id: UUID | None = Query(None, description="Filter by organization"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> TeamListResponse:
    """
    List teams.

    If organization_id is provided, lists teams in that organization.
    Otherwise, lists teams the current user is a member of.
    """
    skip = (page - 1) * page_size

    if organization_id:
        # Check if user is member of the organization
        is_member = await OrganizationService.is_member(
            db, organization_id, current_user.id
        )
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )

        teams, total = await TeamService.list_organization_teams(
            db, organization_id, skip=skip, limit=page_size
        )
    else:
        teams, total = await TeamService.list_user_teams(
            db, current_user.id, skip=skip, limit=page_size
        )

    return TeamListResponse(
        items=list(teams),
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/{team_id}", response_model=TeamWithMembers)
async def get_team(
    team_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamWithMembers:
    """Get team details by ID."""
    team = await TeamService.get_by_id(db, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if user is member of the organization
    is_org_member = await OrganizationService.is_member(
        db, team.organization_id, current_user.id
    )
    if not is_org_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this team",
        )

    # Get member count
    member_count = await TeamService.get_member_count(db, team_id)

    return TeamWithMembers(
        **team.__dict__,
        member_count=member_count,
    )


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: UUID,
    team_in: TeamUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamResponse:
    """Update team information."""
    team = await TeamService.get_by_id(db, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if user is member of the organization
    is_org_member = await OrganizationService.is_member(
        db, team.organization_id, current_user.id
    )
    if not is_org_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this team",
        )

    updated_team = await TeamService.update(db, team, team_in)
    await db.commit()
    await db.refresh(updated_team)

    return updated_team


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a team."""
    team = await TeamService.get_by_id(db, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if user is member of the organization
    is_org_member = await OrganizationService.is_member(
        db, team.organization_id, current_user.id
    )
    if not is_org_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this team",
        )

    await TeamService.delete(db, team)
    await db.commit()


@router.post("/{team_id}/members", status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: UUID,
    member_in: AddTeamMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Add a member to a team."""
    team = await TeamService.get_by_id(db, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if current user is member of the organization
    is_org_member = await OrganizationService.is_member(
        db, team.organization_id, current_user.id
    )
    if not is_org_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this team",
        )

    # Check if user to add exists
    user_to_add = await UserService.get_by_id(db, member_in.user_id)
    if not user_to_add:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Check if user to add is member of the organization
    is_user_org_member = await OrganizationService.is_member(
        db, team.organization_id, member_in.user_id
    )
    if not is_user_org_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a member of the organization",
        )

    # Check if user is already a team member
    is_already_member = await TeamService.is_member(db, team_id, member_in.user_id)
    if is_already_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this team",
        )

    await TeamService.add_member(db, team_id, member_in.user_id)
    await db.commit()

    return {"message": "Member added successfully"}


@router.delete("/{team_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: UUID,
    member_in: RemoveTeamMemberRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Remove a member from a team."""
    team = await TeamService.get_by_id(db, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if current user is member of the organization
    is_org_member = await OrganizationService.is_member(
        db, team.organization_id, current_user.id
    )
    if not is_org_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this team",
        )

    # Check if user is a team member
    is_member = await TeamService.is_member(db, team_id, member_in.user_id)
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a member of this team",
        )

    await TeamService.remove_member(db, team_id, member_in.user_id)
    await db.commit()


@router.get("/{team_id}/members", response_model=list[UserResponse])
async def list_team_members(
    team_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> list[UserResponse]:
    """List members of a team."""
    team = await TeamService.get_by_id(db, team_id)

    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    # Check if user is member of the organization
    is_org_member = await OrganizationService.is_member(
        db, team.organization_id, current_user.id
    )
    if not is_org_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view team members",
        )

    skip = (page - 1) * page_size
    members, _total = await TeamService.list_team_members(
        db, team_id, skip=skip, limit=page_size
    )

    return list(members)
