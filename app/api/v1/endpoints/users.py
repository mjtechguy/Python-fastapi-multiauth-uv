"""User management endpoints."""

from math import ceil
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_superuser, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserListResponse, UserPasswordUpdate, UserResponse, UserUpdate
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update current user profile."""
    user = await UserService.update(db, current_user, user_update)
    await db.commit()
    return user


@router.put("/me/password", response_model=UserResponse)
async def update_password(
    password_update: UserPasswordUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update current user password."""
    # Verify current password
    if not await UserService.verify_password(current_user, password_update.current_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    user = await UserService.update_password(db, current_user, password_update.new_password)
    await db.commit()
    return user


@router.get("", response_model=UserListResponse, dependencies=[Depends(get_current_superuser)])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    is_superuser: bool | None = Query(None, description="Filter by superuser status"),
) -> UserListResponse:
    """List all users (superuser only).

    Optionally filter by superuser status to list only global admins.
    """
    skip = (page - 1) * page_size
    users, total = await UserService.list_users(
        db, skip=skip, limit=page_size, is_superuser=is_superuser
    )

    return UserListResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        pages=ceil(total / page_size),
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get user by ID."""
    user = await UserService.get_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


@router.post("/{user_id}/superuser", response_model=UserResponse)
async def grant_superuser(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> User:
    """Grant superuser (global admin) status to a user.

    Only superusers can grant superuser status to other users.
    This gives the user full access to all system resources and operations.
    """
    user = await UserService.get_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a superuser",
        )

    user.is_superuser = True
    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}/superuser", response_model=UserResponse)
async def revoke_superuser(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> User:
    """Revoke superuser (global admin) status from a user.

    Only superusers can revoke superuser status.
    Cannot revoke your own superuser status.
    """
    user = await UserService.get_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a superuser",
        )

    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke your own superuser status",
        )

    user.is_superuser = False
    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> None:
    """Delete user (superuser only)."""
    user = await UserService.get_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await UserService.delete(db, user)
    await db.commit()
