"""Notification management endpoints."""

import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationBroadcastRequest,
    NotificationBroadcastResponse,
    NotificationCreate,
    NotificationDeleteResponse,
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification(
    data: NotificationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    """
    Create a notification for the current user.

    This endpoint allows users to create notifications for themselves,
    which can be useful for reminders or testing.
    """
    try:
        notification = await NotificationService.create_notification(
            db=db,
            user_id=current_user.id,
            notification_type=data.type,
            title=data.title,
            message=data.message,
            action_url=data.action_url,
            action_label=data.action_label,
            extra_data=data.extra_data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return NotificationResponse.model_validate(notification)


@router.get(
    "",
    response_model=NotificationListResponse,
)
async def list_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    unread_only: bool = Query(False, description="Only return unread notifications"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
) -> NotificationListResponse:
    """
    List notifications for the current user.

    Query Parameters:
        unread_only: Only return unread notifications (default: false)
        page: Page number for pagination (default: 1)
        page_size: Number of items per page (default: 50, max: 100)
    """
    skip = (page - 1) * page_size

    notifications, total = await NotificationService.list_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=page_size,
    )

    unread_count = await NotificationService.get_unread_count(db, current_user.id)

    pages = math.ceil(total / page_size) if total > 0 else 1

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/unread-count",
    response_model=NotificationUnreadCountResponse,
)
async def get_unread_count(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationUnreadCountResponse:
    """
    Get count of unread notifications for the current user.

    Useful for displaying notification badges in UI.
    """
    unread_count = await NotificationService.get_unread_count(db, current_user.id)

    return NotificationUnreadCountResponse(unread_count=unread_count)


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
)
async def get_notification(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    """Get details of a specific notification."""
    notification = await NotificationService.get_notification_by_id(
        db, notification_id, current_user.id
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return NotificationResponse.model_validate(notification)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_as_read(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationResponse:
    """Mark a notification as read."""
    try:
        notification = await NotificationService.mark_as_read(
            db, notification_id, current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return NotificationResponse.model_validate(notification)


@router.post(
    "/mark-all-read",
    response_model=NotificationMarkAllReadResponse,
)
async def mark_all_as_read(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationMarkAllReadResponse:
    """Mark all notifications as read for the current user."""
    count = await NotificationService.mark_all_as_read(db, current_user.id)

    return NotificationMarkAllReadResponse(
        message=f"Marked {count} notification(s) as read",
        count=count,
    )


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_notification(
    notification_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a specific notification."""
    success = await NotificationService.delete_notification(
        db, notification_id, current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )


@router.delete(
    "/read/all",
    response_model=NotificationDeleteResponse,
)
async def delete_read_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationDeleteResponse:
    """Delete all read notifications for the current user."""
    count = await NotificationService.delete_read_notifications(db, current_user.id)

    return NotificationDeleteResponse(
        message=f"Deleted {count} read notification(s)",
        count=count,
    )


@router.post(
    "/broadcast",
    response_model=NotificationBroadcastResponse,
    status_code=status.HTTP_201_CREATED,
)
async def broadcast_notification(
    data: NotificationBroadcastRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NotificationBroadcastResponse:
    """
    Broadcast a notification to multiple users.

    **Requires superuser permissions.**

    This endpoint allows administrators to send the same notification
    to multiple users at once.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can broadcast notifications",
        )

    notifications = await NotificationService.broadcast_to_users(
        db=db,
        user_ids=data.user_ids,
        type=data.type,
        title=data.title,
        message=data.message,
        action_url=data.action_url,
        action_label=data.action_label,
        extra_data=data.extra_data,
    )

    return NotificationBroadcastResponse(
        message=f"Successfully sent notification to {len(notifications)} user(s)",
        notifications_created=len(notifications),
    )
