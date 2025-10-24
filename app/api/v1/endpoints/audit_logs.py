"""Audit log endpoints for security and compliance."""

import math
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_log import (
    AuditLogDetailResponse,
    AuditLogListResponse,
    AuditLogResponse,
    AuditLogStatistics,
    LoginHistoryResponse,
)
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get(
    "",
    response_model=AuditLogListResponse,
)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    user_id: UUID | None = Query(None, description="Filter by user ID"),
    action: str | None = Query(None, description="Filter by action"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    resource_id: str | None = Query(None, description="Filter by resource ID"),
    status: str | None = Query(None, description="Filter by status (success, failure, error)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
) -> AuditLogListResponse:
    """
    List audit logs with optional filters.

    **Permissions:**
    - Superusers can view all audit logs
    - Regular users can only view their own audit logs

    Query Parameters:
        user_id: Filter by user ID (superusers only)
        action: Filter by action
        resource_type: Filter by resource type
        resource_id: Filter by resource ID
        status: Filter by status
        page: Page number for pagination
        page_size: Items per page (max: 500)
    """
    # Authorization: non-superusers can only see their own logs
    if not current_user.is_superuser:
        if user_id and user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own audit logs",
            )
        user_id = current_user.id

    skip = (page - 1) * page_size

    audit_logs, total = await AuditLogService.list_audit_logs(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        status=status,
        skip=skip,
        limit=page_size,
    )

    pages = math.ceil(total / page_size) if total > 0 else 1

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in audit_logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/me",
    response_model=AuditLogListResponse,
)
async def list_my_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
) -> AuditLogListResponse:
    """
    List audit logs for the current user.

    Shows all actions performed by the authenticated user.
    """
    skip = (page - 1) * page_size

    audit_logs, total = await AuditLogService.list_user_audit_logs(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=page_size,
    )

    pages = math.ceil(total / page_size) if total > 0 else 1

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in audit_logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/me/login-history",
    response_model=LoginHistoryResponse,
)
async def get_my_login_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = Query(10, ge=1, le=50, description="Number of records"),
) -> LoginHistoryResponse:
    """
    Get recent successful login history for the current user.

    Shows the most recent successful logins with IP addresses and timestamps.
    Useful for users to review their account activity.
    """
    login_logs = await AuditLogService.get_login_history(
        db=db,
        user_id=current_user.id,
        limit=limit,
    )

    return LoginHistoryResponse(
        items=[AuditLogResponse.model_validate(log) for log in login_logs],
        total=len(login_logs),
    )


@router.get(
    "/resource/{resource_type}/{resource_id}",
    response_model=AuditLogListResponse,
)
async def list_resource_audit_logs(
    resource_type: str,
    resource_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
) -> AuditLogListResponse:
    """
    List audit logs for a specific resource.

    **Requires superuser permissions.**

    Shows all actions performed on a specific resource (e.g., organization, user, file).
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view resource audit logs",
        )

    skip = (page - 1) * page_size

    audit_logs, total = await AuditLogService.list_resource_audit_logs(
        db=db,
        resource_type=resource_type,
        resource_id=resource_id,
        skip=skip,
        limit=page_size,
    )

    pages = math.ceil(total / page_size) if total > 0 else 1

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in audit_logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/search",
    response_model=AuditLogListResponse,
)
async def search_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(..., min_length=1, description="Search term"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(100, ge=1, le=500, description="Items per page"),
) -> AuditLogListResponse:
    """
    Search audit logs by action or resource type.

    **Requires superuser permissions.**

    Searches through action and resource_type fields.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can search all audit logs",
        )

    skip = (page - 1) * page_size

    audit_logs, total = await AuditLogService.search_audit_logs(
        db=db,
        search_term=q,
        skip=skip,
        limit=page_size,
    )

    pages = math.ceil(total / page_size) if total > 0 else 1

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in audit_logs],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get(
    "/statistics",
    response_model=AuditLogStatistics,
)
async def get_audit_statistics(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
) -> AuditLogStatistics:
    """
    Get audit log statistics.

    **Requires superuser permissions.**

    Returns aggregated statistics including:
    - Total logs
    - Breakdown by status (success/failure/error)
    - Unique users count
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view audit statistics",
        )

    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    stats = await AuditLogService.get_statistics(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
    )

    return AuditLogStatistics(**stats)


@router.get(
    "/{audit_log_id}",
    response_model=AuditLogDetailResponse,
)
async def get_audit_log(
    audit_log_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AuditLogDetailResponse:
    """
    Get details of a specific audit log entry.

    **Permissions:**
    - Superusers can view any audit log
    - Regular users can only view their own audit logs
    """
    audit_log = await AuditLogService.get_audit_log_by_id(db, audit_log_id)

    if not audit_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit log not found",
        )

    # Authorization check
    if not current_user.is_superuser and audit_log.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own audit logs",
        )

    # Build detailed response
    response_data = AuditLogDetailResponse.model_validate(audit_log)

    # Add user information if available
    if audit_log.user:
        response_data.user_email = audit_log.user.email
        response_data.user_name = audit_log.user.full_name

    return response_data


@router.get(
    "/users/{user_id}/failed-logins",
    response_model=AuditLogListResponse,
)
async def get_failed_login_attempts(
    user_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    hours: int = Query(24, ge=1, le=168, description="Look back period in hours"),
) -> AuditLogListResponse:
    """
    Get recent failed login attempts for a user.

    **Permissions:**
    - Superusers can view failed logins for any user
    - Regular users can only view their own failed login attempts

    Useful for detecting potential security issues or brute force attacks.
    """
    # Authorization check
    if not current_user.is_superuser and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own login attempts",
        )

    failed_logins = await AuditLogService.get_recent_failed_logins(
        db=db,
        user_id=user_id,
        hours=hours,
    )

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(log) for log in failed_logins],
        total=len(failed_logins),
        page=1,
        page_size=len(failed_logins),
        pages=1,
    )
