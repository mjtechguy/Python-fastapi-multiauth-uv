"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    Token,
    LoginRequest,
    RefreshTokenRequest,
    OAuthCallback,
    OAuthURLResponse,
)
from app.schemas.user import UserCreate, UserResponse
from app.schemas.token import (
    RequestPasswordResetRequest,
    RequestPasswordResetResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
)
from app.services.auth import AuthService
from app.services.user import UserService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new user with email and password.

    Args:
        user_in: User registration data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If email already exists
    """
    # Check if user exists
    existing_user = await UserService.get_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if user_in.username:
        existing_username = await UserService.get_by_username(db, user_in.username)
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    # Create user
    user = await UserService.create(db, user_in)
    await db.flush()

    # Check if this is the first user - make them superuser (global admin)
    from sqlalchemy import select, func

    user_count = await db.execute(select(func.count(User.id)))
    total_users = user_count.scalar_one()

    if total_users == 1:
        # First user becomes superuser (global admin)
        user.is_superuser = True
        await db.flush()

    # Add user to default organization
    from app.services.organization import OrganizationService

    default_org = await OrganizationService.get_or_create_default(db)

    # Set owner_id if this is the first user
    if default_org.owner_id is None:
        default_org.owner_id = user.id
        await db.flush()

    # Add user as member
    await OrganizationService.add_member(db, default_org.id, user.id)

    # Create email verification token and send email
    from app.models.token import EmailVerificationToken
    from app.tasks.email import send_verification_email

    token = EmailVerificationToken.generate_token()
    verification_token = EmailVerificationToken(
        user_id=user.id,
        token=token,
        expires_at=EmailVerificationToken.get_expiration(),
    )
    db.add(verification_token)
    await db.commit()

    # Send verification email asynchronously
    send_verification_email.delay(user.email, token)

    return user


@router.post("/login", response_model=Token)
async def login(
    credentials: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Login with email and password.

    Args:
        credentials: Login credentials
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    user, token = await AuthService.authenticate_local(
        db, credentials.email, credentials.password
    )

    if not user or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Refresh access token using refresh token.

    Args:
        refresh_request: Refresh token request
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid
    """
    token = await AuthService.refresh_access_token(db, refresh_request.refresh_token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user
    """
    return current_user


@router.get("/oauth/{provider}/authorize", response_model=OAuthURLResponse)
async def oauth_authorize(provider: str) -> OAuthURLResponse:
    """
    Get OAuth authorization URL for provider with CSRF protection.

    Generates a secure state parameter that is stored in Redis with 10-minute expiration.
    The state must be validated in the callback to prevent CSRF attacks.

    Args:
        provider: OAuth provider name (google, github, microsoft)

    Returns:
        Authorization URL with state parameter

    Raises:
        HTTPException: If provider is not supported
    """
    import secrets
    from app.services.cache import cache

    try:
        # Generate secure random state for CSRF protection
        state = secrets.token_urlsafe(32)

        # Store state in Redis with 10-minute expiration
        await cache.set(f"oauth_state:{state}", provider, ex=600)

        # Get OAuth client and create authorization URL
        client = await AuthService.get_oauth_client(provider)
        authorize_url = AuthService.get_oauth_authorize_url(provider)

        # Include state parameter in OAuth URL
        authorization_url, _ = client.create_authorization_url(
            authorize_url,
            state=state
        )

        return OAuthURLResponse(authorization_url=authorization_url)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/oauth/{provider}/callback", response_model=Token)
async def oauth_callback(
    provider: str,
    callback: OAuthCallback,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Handle OAuth callback and authenticate user with CSRF protection.

    Validates the state parameter to ensure the request originated from our
    authorization endpoint, preventing CSRF attacks.

    Args:
        provider: OAuth provider name
        callback: OAuth callback data (code and state)
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If state validation fails or authentication fails
    """
    from app.services.cache import cache
    from app.core.logging_config import get_logger

    logger = get_logger(__name__)

    # Validate state parameter (CSRF protection)
    cached_provider = await cache.get(f"oauth_state:{callback.state}")

    if not cached_provider:
        logger.warning(
            "oauth_csrf_invalid_state",
            provider=provider,
            state_exists=False
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter. Please try again.",
        )

    # Verify provider matches
    if cached_provider.decode('utf-8') != provider:
        logger.warning(
            "oauth_csrf_provider_mismatch",
            expected_provider=cached_provider.decode('utf-8'),
            received_provider=provider
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider mismatch. Possible CSRF attack detected.",
        )

    # Delete state after successful validation (one-time use)
    await cache.delete(f"oauth_state:{callback.state}")

    # Proceed with OAuth authentication
    user, token = await AuthService.authenticate_oauth(db, provider, callback.code)

    if not user or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth authentication failed",
        )

    logger.info(
        "oauth_authentication_successful",
        provider=provider,
        user_id=str(user.id)
    )

    return token


@router.post("/keycloak/callback", response_model=Token)
async def keycloak_callback(
    access_token: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Authenticate user via Keycloak access token.

    Args:
        access_token: Keycloak access token
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If authentication fails
    """
    user, token = await AuthService.authenticate_keycloak(db, access_token)

    if not user or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Keycloak authentication failed",
        )

    return token


@router.post("/request-password-reset", response_model=RequestPasswordResetResponse)
async def request_password_reset(
    request: RequestPasswordResetRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RequestPasswordResetResponse:
    """
    Request password reset email.

    Sends a password reset link to the user's email if the account exists.
    Always returns success to prevent email enumeration.

    Args:
        request: Password reset request with email
        db: Database session

    Returns:
        Success message
    """
    from datetime import datetime
    from sqlalchemy import select
    from app.models.token import PasswordResetToken
    from app.tasks.email import send_password_reset_email

    # Get user by email
    user = await UserService.get_by_email(db, request.email)

    if user:
        # Create reset token
        token = PasswordResetToken.generate_token()
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=PasswordResetToken.get_expiration(),
        )
        db.add(reset_token)
        await db.commit()

        # Send email asynchronously
        send_password_reset_email.delay(user.email, token)

    # Always return success (prevent email enumeration)
    return RequestPasswordResetResponse(
        message="If an account with that email exists, a password reset link has been sent.",
        email=request.email,
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResetPasswordResponse:
    """
    Reset password using token.

    Args:
        request: Reset password request with token and new password
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or expired
    """
    from sqlalchemy import select
    from app.models.token import PasswordResetToken
    from app.core.security import get_password_hash

    # Find token
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == request.token)
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token or not reset_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Get user
    user = await UserService.get_by_id(db, reset_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Update password
    user.hashed_password = get_password_hash(request.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    # Mark token as used
    reset_token.used = True

    await db.commit()

    return ResetPasswordResponse(message="Password has been reset successfully")


@router.post("/verify-email", response_model=VerifyEmailResponse)
async def verify_email(
    request: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VerifyEmailResponse:
    """
    Verify email address using token.

    Args:
        request: Email verification request with token
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If token is invalid or expired
    """
    from sqlalchemy import select
    from app.models.token import EmailVerificationToken

    # Find token
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == request.token)
    )
    verification_token = result.scalar_one_or_none()

    if not verification_token or not verification_token.is_valid():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Get user
    user = await UserService.get_by_id(db, verification_token.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Mark user as verified
    user.is_verified = True

    # Mark token as used
    verification_token.used = True

    await db.commit()

    return VerifyEmailResponse(message="Email has been verified successfully")


@router.post("/resend-verification", response_model=ResendVerificationResponse)
async def resend_verification(
    request: ResendVerificationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResendVerificationResponse:
    """
    Resend email verification link.

    Args:
        request: Resend verification request with email
        db: Database session

    Returns:
        Success message
    """
    from sqlalchemy import select
    from app.models.token import EmailVerificationToken
    from app.tasks.email import send_verification_email

    # Get user by email
    user = await UserService.get_by_email(db, request.email)

    if user and not user.is_verified:
        # Create verification token
        token = EmailVerificationToken.generate_token()
        verification_token = EmailVerificationToken(
            user_id=user.id,
            token=token,
            expires_at=EmailVerificationToken.get_expiration(),
        )
        db.add(verification_token)
        await db.commit()

        # Send email asynchronously
        send_verification_email.delay(user.email, token)

    # Always return success (prevent email enumeration)
    return ResendVerificationResponse(
        message="If an account with that email exists and is unverified, a verification link has been sent.",
        email=request.email,
    )
