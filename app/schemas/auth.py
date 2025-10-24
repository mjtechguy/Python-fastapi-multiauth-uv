"""Authentication schemas."""

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Token payload schema."""

    sub: str
    type: str


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""

    refresh_token: str


class OAuthCallback(BaseModel):
    """OAuth callback schema."""

    code: str
    state: str  # Required for CSRF protection


class OAuthURLResponse(BaseModel):
    """OAuth authorization URL response."""

    authorization_url: str


class PasswordResetRequest(BaseModel):
    """Password reset request schema."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation schema."""

    token: str
    new_password: str


class EmailVerificationRequest(BaseModel):
    """Email verification request schema."""

    token: str


class MFAChallengeResponse(BaseModel):
    """MFA challenge response schema."""

    mfa_required: bool = True
    mfa_token: str
    message: str = "Multi-factor authentication required"


class MFAVerifyRequest(BaseModel):
    """MFA verification request schema."""

    mfa_token: str
    totp_code: str
