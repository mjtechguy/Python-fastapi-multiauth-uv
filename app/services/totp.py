"""TOTP service for two-factor authentication."""

import base64
import io
from datetime import UTC, datetime
from uuid import UUID

import pyotp
import qrcode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import encryption_service
from app.core.security import get_password_hash, verify_password
from app.models.totp import TOTPSecret
from app.models.user import User


class TOTPService:
    """Service for TOTP-based two-factor authentication."""

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret."""
        return pyotp.random_base32()

    @staticmethod
    def get_totp_uri(secret: str, user_email: str) -> str:
        """
        Generate TOTP provisioning URI for QR code.

        Args:
            secret: TOTP secret
            user_email: User's email for the URI

        Returns:
            TOTP URI string
        """
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=user_email,
            issuer_name=settings.APP_NAME
        )

    @staticmethod
    def generate_qr_code(uri: str) -> str:
        """
        Generate QR code image as base64 string.

        Args:
            uri: TOTP provisioning URI

        Returns:
            Base64-encoded PNG image
        """
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    @staticmethod
    def verify_totp(secret: str, token: str) -> bool:
        """
        Verify TOTP token.

        Args:
            secret: TOTP secret
            token: 6-digit TOTP token

        Returns:
            True if token is valid
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)  # Allow 1 window before/after

    @staticmethod
    async def setup_totp(
        db: AsyncSession, user: User, device_name: str | None = None
    ) -> tuple[TOTPSecret, str, str, list[str]]:
        """
        Set up TOTP for a user.

        Args:
            db: Database session
            user: User to set up TOTP for
            device_name: Optional device name

        Returns:
            Tuple of (TOTPSecret, provisioning_uri, qr_code_base64, plaintext_backup_codes)
        """
        # Check if TOTP already exists
        result = await db.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == user.id)
        )
        existing = result.scalar_one_or_none()

        if existing and existing.is_enabled:
            raise ValueError("TOTP already enabled for this user")

        # Generate new secret
        secret = TOTPService.generate_secret()
        encrypted_secret = encryption_service.encrypt(secret)

        # Generate backup codes
        backup_codes = TOTPSecret.generate_backup_codes()
        hashed_backup_codes = [get_password_hash(code) for code in backup_codes]

        if existing:
            # Update existing
            existing.encrypted_secret = encrypted_secret
            existing.backup_codes = hashed_backup_codes
            existing.device_name = device_name
            existing.is_enabled = False
            existing.is_verified = False
            totp_secret = existing
        else:
            # Create new
            totp_secret = TOTPSecret(
                user_id=user.id,
                encrypted_secret=encrypted_secret,
                backup_codes=hashed_backup_codes,
                device_name=device_name,
            )
            db.add(totp_secret)

        await db.flush()
        await db.refresh(totp_secret)

        # Generate provisioning URI and QR code
        uri = TOTPService.get_totp_uri(secret, user.email)
        qr_code = TOTPService.generate_qr_code(uri)

        # Return plaintext backup codes (only time they're ever returned)
        return totp_secret, uri, qr_code, backup_codes

    @staticmethod
    async def enable_totp(
        db: AsyncSession, user: User, token: str
    ) -> TOTPSecret:
        """
        Enable TOTP after verifying the initial token.

        Args:
            db: Database session
            user: User to enable TOTP for
            token: Verification token

        Returns:
            Enabled TOTPSecret

        Raises:
            ValueError: If TOTP not set up or token invalid
        """
        result = await db.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == user.id)
        )
        totp_secret = result.scalar_one_or_none()

        if not totp_secret:
            raise ValueError("TOTP not set up for this user")

        if totp_secret.is_enabled:
            raise ValueError("TOTP already enabled")

        # Decrypt secret and verify token
        decrypted_secret = encryption_service.decrypt(totp_secret.encrypted_secret)
        if not TOTPService.verify_totp(decrypted_secret, token):
            raise ValueError("Invalid TOTP token")

        # Enable TOTP
        totp_secret.is_enabled = True
        totp_secret.is_verified = True
        totp_secret.enabled_at = datetime.now(UTC)

        await db.flush()
        await db.refresh(totp_secret)

        return totp_secret

    @staticmethod
    async def disable_totp(
        db: AsyncSession, user: User, password: str
    ) -> None:
        """
        Disable TOTP for a user.

        Args:
            db: Database session
            user: User to disable TOTP for
            password: User's password for verification

        Raises:
            ValueError: If password incorrect or TOTP not enabled
        """
        from app.services.user import UserService

        # Verify password
        if not await UserService.verify_password(user, password):
            raise ValueError("Invalid password")

        result = await db.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == user.id)
        )
        totp_secret = result.scalar_one_or_none()

        if not totp_secret or not totp_secret.is_enabled:
            raise ValueError("TOTP not enabled for this user")

        # Delete TOTP secret
        await db.delete(totp_secret)
        await db.flush()

    @staticmethod
    async def verify_totp_for_user(
        db: AsyncSession, user: User, token: str
    ) -> bool:
        """
        Verify TOTP token for a user.

        Args:
            db: Database session
            user: User to verify TOTP for
            token: TOTP token or backup code

        Returns:
            True if token is valid
        """
        result = await db.execute(
            select(TOTPSecret).where(
                TOTPSecret.user_id == user.id,
                TOTPSecret.is_enabled
            )
        )
        totp_secret = result.scalar_one_or_none()

        if not totp_secret:
            return False

        # Decrypt secret and try TOTP token first
        decrypted_secret = encryption_service.decrypt(totp_secret.encrypted_secret)
        if TOTPService.verify_totp(decrypted_secret, token):
            totp_secret.last_used_at = datetime.now(UTC)
            await db.flush()
            return True

        # Try backup codes
        for hashed_code in totp_secret.backup_codes:
            if verify_password(token, hashed_code):
                # Remove used backup code
                totp_secret.backup_codes.remove(hashed_code)
                totp_secret.last_used_at = datetime.now(UTC)
                await db.flush()
                return True

        return False

    @staticmethod
    async def get_totp_secret(
        db: AsyncSession, user_id: UUID
    ) -> TOTPSecret | None:
        """Get TOTP secret for a user."""
        result = await db.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def regenerate_backup_codes(
        db: AsyncSession, user: User, password: str
    ) -> list[str]:
        """
        Regenerate backup codes for a user.

        Args:
            db: Database session
            user: User to regenerate codes for
            password: User's password for verification

        Returns:
            List of new backup codes (plain text)

        Raises:
            ValueError: If password incorrect or TOTP not enabled
        """
        from app.services.user import UserService

        # Verify password
        if not await UserService.verify_password(user, password):
            raise ValueError("Invalid password")

        result = await db.execute(
            select(TOTPSecret).where(
                TOTPSecret.user_id == user.id,
                TOTPSecret.is_enabled
            )
        )
        totp_secret = result.scalar_one_or_none()

        if not totp_secret:
            raise ValueError("TOTP not enabled for this user")

        # Generate new backup codes
        backup_codes = TOTPSecret.generate_backup_codes()
        hashed_backup_codes = [get_password_hash(code) for code in backup_codes]

        totp_secret.backup_codes = hashed_backup_codes
        await db.flush()

        return backup_codes
