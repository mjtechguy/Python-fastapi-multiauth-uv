"""TOTP schemas for 2FA."""

from datetime import datetime

from pydantic import BaseModel, Field


class TOTPSetupRequest(BaseModel):
    """Request to set up TOTP."""

    device_name: str | None = Field(None, max_length=255)


class TOTPSetupResponse(BaseModel):
    """Response for TOTP setup."""

    secret: str
    provisioning_uri: str
    qr_code: str
    backup_codes: list[str]


class TOTPEnableRequest(BaseModel):
    """Request to enable TOTP."""

    token: str = Field(min_length=6, max_length=6)


class TOTPVerifyRequest(BaseModel):
    """Request to verify TOTP token."""

    token: str = Field(min_length=6, max_length=8)


class TOTPDisableRequest(BaseModel):
    """Request to disable TOTP."""

    password: str


class TOTPStatusResponse(BaseModel):
    """TOTP status response."""

    is_enabled: bool
    is_verified: bool
    device_name: str | None
    enabled_at: datetime | None
    last_used_at: datetime | None
    backup_codes_remaining: int

    model_config = {"from_attributes": True}


class RegenerateBackupCodesRequest(BaseModel):
    """Request to regenerate backup codes."""

    password: str


class RegenerateBackupCodesResponse(BaseModel):
    """Response with new backup codes."""

    backup_codes: list[str]
