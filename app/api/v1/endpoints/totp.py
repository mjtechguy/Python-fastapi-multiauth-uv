"""TOTP (2FA) endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.totp import (
    RegenerateBackupCodesRequest,
    RegenerateBackupCodesResponse,
    TOTPDisableRequest,
    TOTPEnableRequest,
    TOTPSetupRequest,
    TOTPSetupResponse,
    TOTPStatusResponse,
    TOTPVerifyRequest,
)
from app.services.totp import TOTPService

router = APIRouter(prefix="/totp", tags=["2fa"])


@router.post("/setup", response_model=TOTPSetupResponse)
async def setup_totp(
    setup_request: TOTPSetupRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TOTPSetupResponse:
    """
    Set up TOTP (2FA) for the current user.

    Returns QR code and backup codes for initial setup.
    """
    try:
        totp_secret, uri, qr_code, backup_codes = await TOTPService.setup_totp(
            db, current_user, setup_request.device_name
        )

        await db.commit()

        return TOTPSetupResponse(
            secret=totp_secret.secret,
            provisioning_uri=uri,
            qr_code=qr_code,
            backup_codes=backup_codes,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/enable", response_model=dict)
async def enable_totp(
    enable_request: TOTPEnableRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Enable TOTP after verifying the initial token.

    User must scan QR code and enter a valid token to enable 2FA.
    """
    try:
        await TOTPService.enable_totp(db, current_user, enable_request.token)
        await db.commit()

        return {"message": "TOTP enabled successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/verify", response_model=dict)
async def verify_totp(
    verify_request: TOTPVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Verify TOTP token or backup code.

    Used during login when 2FA is enabled.
    """
    is_valid = await TOTPService.verify_totp_for_user(
        db, current_user, verify_request.token
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP token or backup code",
        )

    await db.commit()

    return {"message": "TOTP verified successfully"}


@router.post("/disable", response_model=dict)
async def disable_totp(
    disable_request: TOTPDisableRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Disable TOTP (2FA) for the current user.

    Requires password verification.
    """
    try:
        await TOTPService.disable_totp(db, current_user, disable_request.password)
        await db.commit()

        return {"message": "TOTP disabled successfully"}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/status", response_model=TOTPStatusResponse)
async def get_totp_status(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TOTPStatusResponse:
    """Get TOTP status for the current user."""
    totp_secret = await TOTPService.get_totp_secret(db, current_user.id)

    if not totp_secret:
        return TOTPStatusResponse(
            is_enabled=False,
            is_verified=False,
            device_name=None,
            enabled_at=None,
            last_used_at=None,
            backup_codes_remaining=0,
        )

    return TOTPStatusResponse(
        is_enabled=totp_secret.is_enabled,
        is_verified=totp_secret.is_verified,
        device_name=totp_secret.device_name,
        enabled_at=totp_secret.enabled_at,
        last_used_at=totp_secret.last_used_at,
        backup_codes_remaining=len(totp_secret.backup_codes),
    )


@router.post("/backup-codes", response_model=RegenerateBackupCodesResponse)
async def regenerate_backup_codes(
    request: RegenerateBackupCodesRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> RegenerateBackupCodesResponse:
    """
    Regenerate backup codes for the current user.

    Requires password verification. Old backup codes will be invalidated.
    """
    try:
        backup_codes = await TOTPService.regenerate_backup_codes(
            db, current_user, request.password
        )
        await db.commit()

        return RegenerateBackupCodesResponse(backup_codes=backup_codes)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
