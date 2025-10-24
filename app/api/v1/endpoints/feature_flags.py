"""Feature flag management endpoints."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.feature_flag import (
    FeatureFlagBulkCheckRequest,
    FeatureFlagBulkCheckResponse,
    FeatureFlagCheckRequest,
    FeatureFlagCheckResponse,
    FeatureFlagCreate,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagTargetingUpdate,
    FeatureFlagUpdate,
)
from app.services.feature_flag import FeatureFlagService

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


@router.post(
    "",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_feature_flag(
    data: FeatureFlagCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeatureFlagResponse:
    """
    Create a new feature flag.

    **Requires superuser permissions.**

    Feature flags allow gradual rollout of new features to specific users or percentages of users.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create feature flags",
        )

    # Check if flag already exists
    existing = await FeatureFlagService.get_flag_by_name(db, data.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Feature flag '{data.name}' already exists",
        )

    flag = await FeatureFlagService.create_flag(
        db=db,
        name=data.name,
        description=data.description,
        is_enabled=data.is_enabled,
    )

    # Update rollout and targeting if provided
    if data.rollout_percentage > 0 or data.targeting_rules:
        flag = await FeatureFlagService.update_flag(
            db=db,
            flag=flag,
            rollout_percentage=data.rollout_percentage,
        )
        if data.targeting_rules:
            flag = await FeatureFlagService.update_flag_targeting(
                db=db,
                flag=flag,
                targeting_rules=data.targeting_rules,
            )

    await db.commit()

    return FeatureFlagResponse.model_validate(flag)


@router.get(
    "",
    response_model=FeatureFlagListResponse,
)
async def list_feature_flags(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    enabled_only: bool = Query(False, description="Only return enabled flags"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
) -> FeatureFlagListResponse:
    """
    List all feature flags.

    **Requires superuser permissions.**

    Query Parameters:
        enabled_only: Only return enabled flags (default: false)
        page: Page number for pagination
        page_size: Items per page (max: 500)
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can list feature flags",
        )

    skip = (page - 1) * page_size

    flags, total = await FeatureFlagService.list_flags(
        db=db,
        enabled_only=enabled_only,
        skip=skip,
        limit=page_size,
    )

    pages = math.ceil(total / page_size) if total > 0 else 1

    return FeatureFlagListResponse(
        items=[FeatureFlagResponse.model_validate(flag) for flag in flags],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/{flag_id}",
    response_model=FeatureFlagResponse,
)
async def get_feature_flag(
    flag_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeatureFlagResponse:
    """
    Get details of a specific feature flag.

    **Requires superuser permissions.**
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view feature flag details",
        )

    flag = await FeatureFlagService.get_flag_by_id(db, flag_id)

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found",
        )

    return FeatureFlagResponse.model_validate(flag)


@router.patch(
    "/{flag_id}",
    response_model=FeatureFlagResponse,
)
async def update_feature_flag(
    flag_id: UUID,
    data: FeatureFlagUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeatureFlagResponse:
    """
    Update a feature flag.

    **Requires superuser permissions.**

    Allows updating the enabled status, rollout percentage, description, and targeting rules.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update feature flags",
        )

    flag = await FeatureFlagService.get_flag_by_id(db, flag_id)

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found",
        )

    # Update fields
    if data.description is not None:
        flag.description = data.description

    if data.is_enabled is not None or data.rollout_percentage is not None:
        flag = await FeatureFlagService.update_flag(
            db=db,
            flag=flag,
            is_enabled=data.is_enabled,
            rollout_percentage=data.rollout_percentage,
        )

    if data.targeting_rules is not None:
        flag = await FeatureFlagService.update_flag_targeting(
            db=db,
            flag=flag,
            targeting_rules=data.targeting_rules,
        )

    await db.commit()
    await db.refresh(flag)

    return FeatureFlagResponse.model_validate(flag)


@router.delete(
    "/{flag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_feature_flag(
    flag_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """
    Delete a feature flag.

    **Requires superuser permissions.**
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete feature flags",
        )

    flag = await FeatureFlagService.get_flag_by_id(db, flag_id)

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found",
        )

    await FeatureFlagService.delete_flag(db, flag)
    await db.commit()


@router.post(
    "/check",
    response_model=FeatureFlagCheckResponse,
)
async def check_feature_flag(
    data: FeatureFlagCheckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeatureFlagCheckResponse:
    """
    Check if a feature flag is enabled for the current user.

    This endpoint allows any authenticated user to check if they have access to a feature.
    Takes into account global enabled status, rollout percentage, and targeting rules.
    """
    is_enabled = await FeatureFlagService.is_enabled(
        db=db,
        flag_name=data.flag_name,
        user_id=current_user.id,
        user_email=current_user.email,
    )

    message = None
    if is_enabled:
        message = f"Feature '{data.flag_name}' is enabled for you"
    else:
        flag = await FeatureFlagService.get_flag_by_name(db, data.flag_name)
        if not flag:
            message = f"Feature flag '{data.flag_name}' does not exist"
        elif not flag.is_enabled:
            message = f"Feature '{data.flag_name}' is not enabled"
        else:
            message = f"Feature '{data.flag_name}' is not enabled for you"

    return FeatureFlagCheckResponse(
        flag_name=data.flag_name,
        is_enabled=is_enabled,
        message=message,
    )


@router.post(
    "/check-bulk",
    response_model=FeatureFlagBulkCheckResponse,
)
async def check_multiple_feature_flags(
    data: FeatureFlagBulkCheckRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeatureFlagBulkCheckResponse:
    """
    Check multiple feature flags at once for the current user.

    Efficient way to check multiple feature flags in a single request.
    Useful for frontend applications that need to check several features.
    """
    flags = {}

    for flag_name in data.flag_names:
        is_enabled = await FeatureFlagService.is_enabled(
            db=db,
            flag_name=flag_name,
            user_id=current_user.id,
            user_email=current_user.email,
        )
        flags[flag_name] = is_enabled

    return FeatureFlagBulkCheckResponse(flags=flags)


@router.put(
    "/{flag_id}/targeting",
    response_model=FeatureFlagResponse,
)
async def update_feature_flag_targeting(
    flag_id: UUID,
    data: FeatureFlagTargetingUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> FeatureFlagResponse:
    """
    Update targeting rules for a feature flag.

    **Requires superuser permissions.**

    Targeting rules format:
    ```json
    {
        "user_ids": ["uuid1", "uuid2"],
        "organization_ids": ["uuid3", "uuid4"],
        "user_emails": ["user@example.com"]
    }
    ```
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update feature flag targeting",
        )

    flag = await FeatureFlagService.get_flag_by_id(db, flag_id)

    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found",
        )

    flag = await FeatureFlagService.update_flag_targeting(
        db=db,
        flag=flag,
        targeting_rules=data.targeting_rules,
    )

    await db.commit()
    await db.refresh(flag)

    return FeatureFlagResponse.model_validate(flag)
