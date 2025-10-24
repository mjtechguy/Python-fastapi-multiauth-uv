"""API Key management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyResponse,
)
from app.services.api_key_service import APIKeyService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post("", response_model=APIKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: APIKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> APIKeyCreateResponse:
    """
    Create a new API key for programmatic access.

    **Important:** The full API key is only shown once! Save it securely.

    API keys can be used in the `X-API-Key` header or `Authorization: Bearer <key>` header.
    """
    api_key, raw_key = await APIKeyService.create_api_key(
        db=db,
        user_id=current_user.id,
        name=data.name,
        expires_in_days=data.expires_in_days,
    )

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.prefix,
        is_active=api_key.is_active,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        key=raw_key,
    )


@router.get("", response_model=APIKeyListResponse)
async def list_api_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    include_inactive: bool = False,
) -> APIKeyListResponse:
    """
    List all API keys for the current user.

    Query Parameters:
        include_inactive: Include revoked/expired keys (default: false)
    """
    keys = await APIKeyService.get_user_api_keys(
        db=db, user_id=current_user.id, include_inactive=include_inactive
    )

    return APIKeyListResponse(
        items=[APIKeyResponse.model_validate(key) for key in keys],
        total=len(keys),
        page=1,
        page_size=len(keys),
        pages=1,
    )


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> APIKeyResponse:
    """Get details of a specific API key."""
    api_key = await APIKeyService.get_api_key_by_id(
        db=db, key_id=key_id, user_id=current_user.id
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    return APIKeyResponse.model_validate(api_key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Revoke (deactivate) an API key.

    The key will be marked as inactive and can no longer be used.
    """
    success = await APIKeyService.revoke_api_key(
        db=db, key_id=key_id, user_id=current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )


@router.delete("/{key_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Permanently delete an API key.

    This action cannot be undone. The key will be completely removed from the database.
    """
    success = await APIKeyService.delete_api_key(
        db=db, key_id=key_id, user_id=current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
