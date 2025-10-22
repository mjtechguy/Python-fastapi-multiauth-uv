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
    await db.commit()

    # TODO: Send verification email
    # from app.tasks.email import send_verification_email
    # send_verification_email.delay(user.email, verification_token)

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
    Get OAuth authorization URL for provider.

    Args:
        provider: OAuth provider name (google, github, microsoft)

    Returns:
        Authorization URL

    Raises:
        HTTPException: If provider is not supported
    """
    try:
        client = await AuthService.get_oauth_client(provider)
        authorize_url = AuthService.get_oauth_authorize_url(provider)

        authorization_url, _ = client.create_authorization_url(authorize_url)

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
    Handle OAuth callback and authenticate user.

    Args:
        provider: OAuth provider name
        callback: OAuth callback data
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If authentication fails
    """
    user, token = await AuthService.authenticate_oauth(db, provider, callback.code)

    if not user or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="OAuth authentication failed",
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
