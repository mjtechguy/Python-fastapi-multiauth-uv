"""Quota checking dependencies for API endpoints."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.organization_helpers import get_user_organization_id
from app.db.session import get_db
from app.models.quota import OrganizationQuota
from app.models.user import User
from app.services.quota import QuotaService

# Optional bearer security for API quota (doesn't fail on missing auth)
optional_security = HTTPBearer(auto_error=False)


async def check_api_quota_optional(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(optional_security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationQuota | None:
    """
    Optional API quota check that only runs for authenticated requests.
    Skips quota enforcement for unauthenticated endpoints (login, register, etc).
    """
    # Skip if no auth credentials
    if not credentials:
        return None

    # Skip quota check for health and metrics endpoints
    if request.url.path.startswith(("/health", "/metrics", "/docs", "/openapi.json", "/auth/")):
        return None

    # Get user from token
    from uuid import UUID

    from app.core.security import verify_token
    from app.services.user import UserService

    token = credentials.credentials
    user_id = verify_token(token, token_type="access")
    if not user_id:
        return None

    current_user = await UserService.get_by_id(db, UUID(user_id))
    if not current_user or not current_user.is_active:
        return None

    # Get user's organization using helper
    try:
        organization_id = get_user_organization_id(current_user)
    except HTTPException:
        # User has no organization - skip quota check
        return None

    # Get or create quota
    quota = await QuotaService.get_or_create_quota(db, organization_id)
    quota = await QuotaService.check_and_reset_monthly_quotas(db, quota)

    # Check if quota exceeded
    if quota.is_api_call_quota_exceeded():
        raise HTTPException(
            status_code=429,
            detail=f"API call quota exceeded. Limit: {quota.max_api_calls_per_month} calls per month. "
                   f"Resets at: {quota.api_calls_reset_at.isoformat()}",
        )

    # Increment counter
    await QuotaService.increment_api_calls(
        db,
        organization_id,
        user_id=current_user.id,
        metadata={"path": request.url.path, "method": request.method}
    )

    return quota


async def check_api_quota(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationQuota:
    """
    Check if organization has exceeded API call quota.
    Increments the API call counter.
    Requires authentication.
    """
    # Skip quota check for health and metrics endpoints
    if request.url.path.startswith(("/health", "/metrics", "/docs", "/openapi.json")):
        # Create a dummy quota object that won't fail
        return OrganizationQuota()

    # Get user's organization using helper (handles organizations relationship)
    organization_id = get_user_organization_id(current_user)

    # Get or create quota
    quota = await QuotaService.get_or_create_quota(db, organization_id)
    quota = await QuotaService.check_and_reset_monthly_quotas(db, quota)

    # Check if quota exceeded
    if quota.is_api_call_quota_exceeded():
        raise HTTPException(
            status_code=429,
            detail=f"API call quota exceeded. Limit: {quota.max_api_calls_per_month} calls per month. "
                   f"Resets at: {quota.api_calls_reset_at.isoformat()}",
        )

    # Increment counter
    await QuotaService.increment_api_calls(
        db,
        organization_id,
        user_id=current_user.id,
        metadata={"path": request.url.path, "method": request.method}
    )

    return quota


async def check_file_upload_quota(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file_size: int = 0,
) -> OrganizationQuota:
    """
    Check if organization has exceeded file upload quota.
    Does NOT increment the counter - that should be done after successful upload.
    """
    organization_id = get_user_organization_id(current_user)

    # Get or create quota
    quota = await QuotaService.get_or_create_quota(db, organization_id)
    quota = await QuotaService.check_and_reset_daily_quotas(db, quota)

    # Check file upload quota
    if quota.is_file_upload_quota_exceeded():
        raise HTTPException(
            status_code=429,
            detail=f"File upload quota exceeded. Limit: {quota.max_file_uploads_per_day} uploads per day. "
                   f"Resets at: {quota.file_uploads_reset_at.isoformat()}",
        )

    # Check file size
    if quota.is_file_size_exceeded(file_size):
        raise HTTPException(
            status_code=413,
            detail=f"File size exceeds limit. Maximum allowed: {quota.max_file_size_bytes} bytes "
                   f"({quota.max_file_size_bytes / 1024 / 1024:.2f} MB)",
        )

    # Check storage quota
    if quota.is_storage_quota_exceeded(file_size):
        raise HTTPException(
            status_code=507,
            detail=f"Storage quota exceeded. Current: {quota.current_storage_bytes} bytes, "
                   f"Limit: {quota.max_storage_bytes} bytes. "
                   f"Additional {file_size} bytes would exceed limit.",
        )

    return quota


async def check_user_quota(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationQuota:
    """
    Check if organization has exceeded user quota.
    Does NOT increment the counter - that should be done after successful user creation.
    """
    organization_id = get_user_organization_id(current_user)

    # Get or create quota
    quota = await QuotaService.get_or_create_quota(db, organization_id)

    # Check user quota
    if quota.is_user_quota_exceeded():
        raise HTTPException(
            status_code=429,
            detail=f"User quota exceeded. Limit: {quota.max_users} users. "
                   f"Current: {quota.current_users} users.",
        )

    return quota
