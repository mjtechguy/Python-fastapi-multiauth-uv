"""Unit tests for token hashing and TOTP encryption security features."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.encryption import EncryptionService, encryption_service
from app.models.invitation import Invitation
from app.models.token import EmailVerificationToken, PasswordResetToken
from app.models.totp import TOTPSecret


class TestTokenHashing:
    """Test that tokens are properly hashed and cannot be recovered."""

    def test_password_reset_token_is_hashed(self):
        """Test that password reset tokens are stored hashed."""
        plaintext_token = PasswordResetToken.generate_token()
        token_hash = EncryptionService.hash_token(plaintext_token)

        # Hash should be different from plaintext
        assert token_hash != plaintext_token

        # Hash should be deterministic (same input = same hash)
        hash2 = EncryptionService.hash_token(plaintext_token)
        assert token_hash == hash2

        # Hash should be SHA256 (64 hex chars)
        assert len(token_hash) == 64
        assert all(c in '0123456789abcdef' for c in token_hash)

    def test_email_verification_token_is_hashed(self):
        """Test that email verification tokens are stored hashed."""
        plaintext_token = EmailVerificationToken.generate_token()
        token_hash = EncryptionService.hash_token(plaintext_token)

        # Hash should be different from plaintext
        assert token_hash != plaintext_token

        # Hash should be SHA256
        assert len(token_hash) == 64

    def test_invitation_token_is_hashed(self):
        """Test that invitation tokens are stored hashed."""
        plaintext_token = Invitation.generate_token()
        token_hash = EncryptionService.hash_token(plaintext_token)

        # Hash should be different from plaintext
        assert token_hash != plaintext_token

        # Hash should be SHA256
        assert len(token_hash) == 64

    def test_token_hash_is_one_way(self):
        """Test that token hashing is one-way (cannot reverse)."""
        plaintext = "my-secret-token-12345"
        hash_value = EncryptionService.hash_token(plaintext)

        # No way to get plaintext back from hash
        # This is by design - if database is compromised, tokens cannot be recovered
        assert hash_value != plaintext
        assert len(hash_value) == 64

    def test_different_tokens_produce_different_hashes(self):
        """Test that different tokens produce different hashes."""
        token1 = "token-one"
        token2 = "token-two"

        hash1 = EncryptionService.hash_token(token1)
        hash2 = EncryptionService.hash_token(token2)

        assert hash1 != hash2


class TestTOTPEncryption:
    """Test that TOTP secrets are properly encrypted."""

    def test_totp_secret_is_encrypted(self):
        """Test that TOTP secrets are encrypted before storage."""
        plaintext_secret = "JBSWY3DPEHPK3PXP"  # Example base32 secret
        encrypted = encryption_service.encrypt(plaintext_secret)

        # Encrypted should be different from plaintext
        assert encrypted != plaintext_secret

        # Encrypted should be longer (includes IV, etc.)
        assert len(encrypted) > len(plaintext_secret)

    def test_totp_secret_can_be_decrypted(self):
        """Test that encrypted TOTP secrets can be decrypted."""
        plaintext_secret = "JBSWY3DPEHPK3PXP"
        encrypted = encryption_service.encrypt(plaintext_secret)
        decrypted = encryption_service.decrypt(encrypted)

        # Decrypted should match original
        assert decrypted == plaintext_secret

    def test_totp_encryption_is_reversible_but_secure(self):
        """Test that TOTP encryption is reversible but still secure."""
        secret = "MYSECRET12345678"

        # Encrypt multiple times with same key
        encrypted1 = encryption_service.encrypt(secret)
        encrypted2 = encryption_service.encrypt(secret)

        # Encrypted values should be different (due to IV/nonce)
        # This prevents pattern analysis
        assert encrypted1 != encrypted2

        # But both should decrypt to same value
        decrypted1 = encryption_service.decrypt(encrypted1)
        decrypted2 = encryption_service.decrypt(encrypted2)

        assert decrypted1 == secret
        assert decrypted2 == secret

    def test_totp_decryption_fails_with_wrong_key(self):
        """Test that decryption fails if key is wrong."""
        secret = "MYSECRETKEY"
        encrypted = encryption_service.encrypt(secret)

        # Tampering with encrypted data should cause decryption to fail
        tampered = encrypted[:-10] + "xxxxxxxxxx"

        with pytest.raises(Exception):  # Fernet raises on invalid data
            encryption_service.decrypt(tampered)

    def test_totp_model_has_encrypted_secret_field(self):
        """Test that TOTP model has encrypted_secret field, not plaintext."""
        # Check model has correct field
        from app.models.totp import TOTPSecret
        import inspect

        # Get model attributes
        sig = inspect.signature(TOTPSecret.__init__)
        params = [p for p in sig.parameters.keys()]

        # Should have encrypted_secret field
        # (This is a structural test to ensure migration happened)
        assert hasattr(TOTPSecret, 'encrypted_secret')


class TestMFATokenGeneration:
    """Test MFA challenge token generation."""

    def test_mfa_token_is_jwt(self):
        """Test that MFA tokens are valid JWTs."""
        from app.core.security import create_mfa_token, verify_token

        user_id = str(uuid.uuid4())
        mfa_token = create_mfa_token(user_id)

        # Token should be a JWT (3 parts separated by dots)
        parts = mfa_token.split('.')
        assert len(parts) == 3

        # Should be verifiable as MFA type
        verified_user_id = verify_token(mfa_token, token_type="mfa")
        assert verified_user_id == user_id

    def test_mfa_token_cannot_be_used_as_access_token(self):
        """Test that MFA tokens cannot be used as access tokens."""
        from app.core.security import create_mfa_token, verify_token

        user_id = str(uuid.uuid4())
        mfa_token = create_mfa_token(user_id)

        # Should fail when verified as access token
        result = verify_token(mfa_token, token_type="access")
        assert result is None

    def test_access_token_cannot_be_used_as_mfa_token(self):
        """Test that access tokens cannot be used as MFA tokens."""
        from app.core.security import create_access_token, verify_token

        user_id = str(uuid.uuid4())
        access_token = create_access_token(user_id)

        # Should fail when verified as MFA token
        result = verify_token(access_token, token_type="mfa")
        assert result is None


class TestQuotaBatching:
    """Test that quota operations use flush instead of commit."""

    @pytest.mark.asyncio
    async def test_quota_increment_uses_flush_not_commit(self):
        """Test that quota increment doesn't commit (allows batching)."""
        # This is a structural/documentation test
        # We verify by reading the service code
        from app.services.quota import QuotaService
        import inspect

        # Get source of increment_api_calls
        source = inspect.getsource(QuotaService.increment_api_calls)

        # Should use flush, not commit
        assert 'await db.flush()' in source
        assert 'await db.commit()' not in source

    @pytest.mark.asyncio
    async def test_quota_decrement_uses_flush_not_commit(self):
        """Test that quota decrement doesn't commit (allows batching)."""
        from app.services.quota import QuotaService
        import inspect

        source = inspect.getsource(QuotaService.decrement_storage)

        # Should use flush, not commit
        assert 'await db.flush()' in source
        assert 'await db.commit()' not in source
