"""Token schemas for email verification and password reset."""

from pydantic import BaseModel, EmailStr, Field


class RequestPasswordResetRequest(BaseModel):
    """Request password reset schema."""

    email: EmailStr = Field(..., description="Email address of the user")


class RequestPasswordResetResponse(BaseModel):
    """Response after requesting password reset."""

    message: str = Field(..., description="Success message")
    email: EmailStr = Field(..., description="Email address where reset link was sent")


class ResetPasswordRequest(BaseModel):
    """Reset password with token schema."""

    token: str = Field(..., min_length=32, description="Password reset token")
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password (min 8 characters)",
    )


class ResetPasswordResponse(BaseModel):
    """Response after resetting password."""

    message: str = Field(..., description="Success message")


class VerifyEmailRequest(BaseModel):
    """Verify email with token schema."""

    token: str = Field(..., min_length=32, description="Email verification token")


class VerifyEmailResponse(BaseModel):
    """Response after verifying email."""

    message: str = Field(..., description="Success message")


class ResendVerificationRequest(BaseModel):
    """Resend verification email schema."""

    email: EmailStr = Field(..., description="Email address of the user")


class ResendVerificationResponse(BaseModel):
    """Response after resending verification email."""

    message: str = Field(..., description="Success message")
    email: EmailStr = Field(..., description="Email address where verification link was sent")
