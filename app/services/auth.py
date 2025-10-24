"""Authentication service supporting multiple auth strategies."""

from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.models.oauth import OAuthAccount
from app.models.user import User
from app.schemas.auth import Token
from app.services.user import UserService


class AuthService:
    """Authentication service with multiple strategies."""

    @staticmethod
    async def authenticate_local(
        db: AsyncSession,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, Token | str] | tuple[None, None]:
        """
        Authenticate user with email and password.

        Returns:
            - (User, Token) if no MFA required
            - (User, mfa_token_string) if MFA required (str indicates MFA challenge)
            - (None, None) if authentication failed
        """
        user = await UserService.get_by_email(db, email)

        if not user:
            return None, None

        if not user.is_active:
            return None, None

        # Check email verification
        if not user.is_verified:
            return None, None

        if await UserService.is_locked(user):
            return None, None

        if not await UserService.verify_password(user, password):
            await UserService.increment_failed_login(db, user)
            await db.commit()
            return None, None

        # Check if MFA is enabled for this user
        from app.services.totp import TOTPService

        totp_secret = await TOTPService.get_totp_secret(db, user.id)

        if totp_secret and totp_secret.is_enabled:
            # Password auth successful, but MFA required
            # Return MFA challenge token (NOT a full access token)
            from app.core.security import create_mfa_token

            mfa_token = create_mfa_token(str(user.id))
            return user, mfa_token

        # No MFA required, proceed with normal login
        await UserService.update_last_login(db, user)
        await db.flush()

        # Create tokens
        access_token_str = create_access_token(str(user.id))
        refresh_token_str = create_refresh_token(str(user.id))

        # Create session with refresh token
        from app.services.session import SessionService

        await SessionService.create_session(
            db=db,
            user=user,
            refresh_token=refresh_token_str,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await db.commit()

        token = Token(
            access_token=access_token_str,
            refresh_token=refresh_token_str,
        )

        return user, token

    @staticmethod
    async def verify_mfa(
        db: AsyncSession,
        mfa_token: str,
        totp_code: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, Token] | tuple[None, None]:
        """
        Verify MFA and complete authentication.

        Args:
            db: Database session
            mfa_token: MFA challenge token from phase 1
            totp_code: TOTP code from authenticator app
            user_agent: User agent string from request
            ip_address: IP address from request

        Returns:
            - (User, Token) if MFA verification successful
            - (None, None) if verification failed
        """
        # Verify MFA token
        user_id = verify_token(mfa_token, token_type="mfa")

        if not user_id:
            return None, None

        from uuid import UUID

        user = await UserService.get_by_id(db, UUID(user_id))

        if not user or not user.is_active or not user.is_verified:
            return None, None

        if await UserService.is_locked(user):
            return None, None

        # Verify TOTP code
        from app.services.totp import TOTPService

        totp_valid = await TOTPService.verify_totp_for_user(db, user, totp_code)

        if not totp_valid:
            # Increment failed login attempts for invalid TOTP
            await UserService.increment_failed_login(db, user)
            await db.commit()
            return None, None

        # MFA verification successful, update last login and issue tokens
        await UserService.update_last_login(db, user)
        await db.flush()

        # Create tokens
        access_token_str = create_access_token(str(user.id))
        refresh_token_str = create_refresh_token(str(user.id))

        # Create session with refresh token
        from app.services.session import SessionService

        await SessionService.create_session(
            db=db,
            user=user,
            refresh_token=refresh_token_str,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await db.commit()

        token = Token(
            access_token=access_token_str,
            refresh_token=refresh_token_str,
        )

        return user, token

    @staticmethod
    async def refresh_access_token(db: AsyncSession, refresh_token: str) -> Token | None:
        """Refresh access token using refresh token."""
        user_id = verify_token(refresh_token, token_type="refresh")

        if not user_id:
            return None

        from uuid import UUID

        user = await UserService.get_by_id(db, UUID(user_id))

        if not user or not user.is_active or not user.is_verified:
            return None

        # Check if user is locked
        if await UserService.is_locked(user):
            return None

        return Token(
            access_token=create_access_token(str(user.id)),
            refresh_token=create_refresh_token(str(user.id)),
        )

    @staticmethod
    async def get_oauth_client(provider: str) -> AsyncOAuth2Client:
        """Get OAuth2 client for the specified provider."""
        if provider == "google":
            return AsyncOAuth2Client(
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                redirect_uri=settings.GOOGLE_REDIRECT_URI,
                scope="openid email profile",
            )
        if provider == "github":
            return AsyncOAuth2Client(
                client_id=settings.GITHUB_CLIENT_ID,
                client_secret=settings.GITHUB_CLIENT_SECRET,
                redirect_uri=settings.GITHUB_REDIRECT_URI,
                scope="read:user user:email",
            )
        if provider == "microsoft":
            return AsyncOAuth2Client(
                client_id=settings.MICROSOFT_CLIENT_ID,
                client_secret=settings.MICROSOFT_CLIENT_SECRET,
                redirect_uri=settings.MICROSOFT_REDIRECT_URI,
                scope="openid email profile",
            )
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    @staticmethod
    def get_oauth_authorize_url(provider: str) -> str:
        """Get OAuth authorization URL for the specified provider."""
        if provider == "google":
            return "https://accounts.google.com/o/oauth2/v2/auth"
        if provider == "github":
            return "https://github.com/login/oauth/authorize"
        if provider == "microsoft":
            return "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    @staticmethod
    def get_oauth_token_url(provider: str) -> str:
        """Get OAuth token URL for the specified provider."""
        if provider == "google":
            return "https://oauth2.googleapis.com/token"
        if provider == "github":
            return "https://github.com/login/oauth/access_token"
        if provider == "microsoft":
            return "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        raise ValueError(f"Unsupported OAuth provider: {provider}")

    @staticmethod
    async def get_oauth_user_info(provider: str, access_token: str) -> dict[str, Any]:
        """Get user info from OAuth provider."""
        async with httpx.AsyncClient() as client:
            if provider == "google":
                response = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                return response.json()
            if provider == "github":
                # Get basic user info
                response = await client.get(
                    "https://api.github.com/user",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                user_info = response.json()

                # GitHub can return email=None, so fetch from /user/emails
                if not user_info.get("email"):
                    emails_response = await client.get(
                        "https://api.github.com/user/emails",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    emails_response.raise_for_status()
                    emails = emails_response.json()

                    # Find primary verified email
                    primary_email = next(
                        (e["email"] for e in emails if e.get("primary") and e.get("verified")),
                        None
                    )
                    # Fallback to first verified email
                    if not primary_email:
                        primary_email = next(
                            (e["email"] for e in emails if e.get("verified")),
                            None
                        )

                    user_info["email"] = primary_email

                return user_info
            if provider == "microsoft":
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                return response.json()
            raise ValueError(f"Unsupported OAuth provider: {provider}")

    @staticmethod
    async def authenticate_oauth(  # noqa: PLR0915
        db: AsyncSession,
        provider: str,
        code: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, Token] | tuple[None, None]:
        """
        Authenticate user via OAuth provider.

        Args:
            db: Database session
            provider: OAuth provider name
            code: Authorization code
            user_agent: User agent string from request
            ip_address: IP address from request

        Returns:
            Tuple of (User, Token) or (None, None) if failed
        """
        try:
            client = await AuthService.get_oauth_client(provider)
            token_url = AuthService.get_oauth_token_url(provider)

            # Exchange code for token
            token = await client.fetch_token(token_url, code=code)
            access_token = token.get("access_token")

            if not access_token:
                return None, None

            # Get user info from provider
            user_info = await AuthService.get_oauth_user_info(provider, access_token)

            # Extract email
            if provider == "google":
                email = user_info.get("email")
                provider_user_id = user_info.get("id")
                name = user_info.get("name")
            elif provider == "github":
                email = user_info.get("email")
                provider_user_id = str(user_info.get("id"))
                name = user_info.get("name")
            elif provider == "microsoft":
                email = user_info.get("userPrincipalName")
                provider_user_id = user_info.get("id")
                name = user_info.get("displayName")
            else:
                return None, None

            if not email or not provider_user_id:
                return None, None

            # Check if OAuth account exists
            result = await db.execute(
                select(OAuthAccount).where(
                    OAuthAccount.provider == provider,
                    OAuthAccount.provider_user_id == provider_user_id,
                )
            )
            oauth_account = result.scalar_one_or_none()

            if oauth_account:
                # Update OAuth account
                oauth_account.access_token = access_token
                oauth_account.refresh_token = token.get("refresh_token")
                oauth_account.provider_data = user_info
                user = await UserService.get_by_id(db, oauth_account.user_id)
            else:
                # Check if user exists by email
                user = await UserService.get_by_email(db, email)

                if not user:
                    # Create new user (email already normalized by get_by_email lookup)
                    user = User(
                        email=email.lower().strip(),
                        full_name=name,
                        is_verified=True,  # OAuth emails are pre-verified
                    )
                    db.add(user)
                    await db.flush()

                    # Add user to default organization (same as email/password registration)
                    from app.services.organization import OrganizationService
                    default_org = await OrganizationService.get_or_create_default_organization(db)
                    await OrganizationService.add_member(db, default_org.id, user.id)

                # Create OAuth account
                oauth_account = OAuthAccount(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    access_token=access_token,
                    refresh_token=token.get("refresh_token"),
                    provider_data=user_info,
                )
                db.add(oauth_account)

            await UserService.update_last_login(db, user)
            await db.flush()

            # Create tokens
            access_token_str = create_access_token(str(user.id))
            refresh_token_str = create_refresh_token(str(user.id))

            # Create session with refresh token
            from app.services.session import SessionService

            await SessionService.create_session(
                db=db,
                user=user,
                refresh_token=refresh_token_str,
                user_agent=user_agent,
                ip_address=ip_address,
            )

            await db.commit()
            await db.refresh(user)

            auth_token = Token(
                access_token=access_token_str,
                refresh_token=refresh_token_str,
            )

            return user, auth_token

        except Exception as e:
            from app.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.error(
                "oauth_authentication_failed",
                provider=provider,
                error=str(e),
                exc_info=True
            )
            return None, None

    @staticmethod
    async def authenticate_keycloak(
        db: AsyncSession, access_token: str
    ) -> tuple[User, Token] | tuple[None, None]:
        """Authenticate user via Keycloak."""
        try:
            from python_keycloak import KeycloakOpenID

            keycloak_openid = KeycloakOpenID(
                server_url=settings.KEYCLOAK_SERVER_URL,
                client_id=settings.KEYCLOAK_CLIENT_ID,
                realm_name=settings.KEYCLOAK_REALM,
                client_secret_key=settings.KEYCLOAK_CLIENT_SECRET,
            )

            # Verify token and get user info
            user_info = keycloak_openid.userinfo(access_token)

            email = user_info.get("email")
            keycloak_id = user_info.get("sub")
            name = user_info.get("name")

            if not email or not keycloak_id:
                return None, None

            # Check if OAuth account exists
            result = await db.execute(
                select(OAuthAccount).where(
                    OAuthAccount.provider == "keycloak",
                    OAuthAccount.provider_user_id == keycloak_id,
                )
            )
            oauth_account = result.scalar_one_or_none()

            if oauth_account:
                oauth_account.access_token = access_token
                oauth_account.provider_data = user_info
                user = await UserService.get_by_id(db, oauth_account.user_id)
            else:
                user = await UserService.get_by_email(db, email)

                if not user:
                    user = User(
                        email=email.lower().strip(),
                        full_name=name,
                        is_verified=True,
                    )
                    db.add(user)
                    await db.flush()

                    # Add user to default organization (same as email/password registration)
                    from app.services.organization import OrganizationService
                    default_org = await OrganizationService.get_or_create_default_organization(db)
                    await OrganizationService.add_member(db, default_org.id, user.id)

                oauth_account = OAuthAccount(
                    user_id=user.id,
                    provider="keycloak",
                    provider_user_id=keycloak_id,
                    access_token=access_token,
                    provider_data=user_info,
                )
                db.add(oauth_account)

            await UserService.update_last_login(db, user)
            await db.commit()
            await db.refresh(user)

            auth_token = Token(
                access_token=create_access_token(str(user.id)),
                refresh_token=create_refresh_token(str(user.id)),
            )

            return user, auth_token

        except Exception as e:
            from app.core.logging_config import get_logger
            logger = get_logger(__name__)
            logger.error(
                "keycloak_authentication_failed",
                error=str(e),
                exc_info=True
            )
            return None, None
