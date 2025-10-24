"""Encryption service for sensitive data using Fernet (symmetric encryption)."""

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import settings


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self):
        """Initialize encryption service with key from settings."""
        # Derive a Fernet-compatible key from the secret key
        # Fernet requires a 32-byte base64-encoded key
        key_bytes = settings.SECRET_KEY.encode()[:32].ljust(32, b'\0')
        key = base64.urlsafe_b64encode(key_bytes)
        self.cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return plaintext

        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt ciphertext string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string

        Raises:
            cryptography.fernet.InvalidToken: If decryption fails
        """
        if not ciphertext:
            return ciphertext

        decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()

    def encrypt_dict(self, data: dict[str, Any]) -> dict[str, str]:
        """
        Encrypt all string values in a dictionary.

        Args:
            data: Dictionary with string values to encrypt

        Returns:
            Dictionary with encrypted values
        """
        return {
            key: self.encrypt(str(value)) if value is not None else None
            for key, value in data.items()
        }

    def decrypt_dict(self, data: dict[str, str]) -> dict[str, str]:
        """
        Decrypt all encrypted values in a dictionary.

        Args:
            data: Dictionary with encrypted values

        Returns:
            Dictionary with decrypted values
        """
        return {
            key: self.decrypt(value) if value is not None else None
            for key, value in data.items()
        }

    @staticmethod
    def hash_token(token: str) -> str:
        """
        Create a cryptographic hash of a token for storage.

        This is used for tokens that need to be validated (lookup by hash)
        but should not be recoverable if the database is compromised.

        Args:
            token: Token to hash

        Returns:
            SHA256 hash of the token (hex format)
        """
        return hashlib.sha256(token.encode()).hexdigest()


# Global encryption service instance
encryption_service = EncryptionService()
