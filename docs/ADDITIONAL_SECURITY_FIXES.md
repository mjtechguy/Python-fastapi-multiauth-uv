# Additional Security Fixes & Recommendations

## Overview

This document outlines additional security improvements beyond the critical crash fixes. These include both **immediate blocking fixes** (completed) and **security hardening recommendations** (requires careful migration).

---

## ✅ Immediate Blocking Fixes (COMPLETED)

### 1. ✅ OAuth Cache Parameter Error
**File**: `app/api/v1/endpoints/auth.py:220`

**Issue**: `cache.set(..., ex=600)` passes unsupported kwarg, causing 500 error before OAuth flow begins.

**Fix**:
```python
# Before (BROKEN):
await cache.set(f"oauth_state:{state}", provider, ex=600)

# After (FIXED):
await cache.set(f"oauth_state:{state}", provider, expire=600)
```

**Impact**: OAuth authorization flows now work correctly.

---

### 2. ✅ OAuth Callback Decode Error
**File**: `app/api/v1/endpoints/auth.py:284`

**Issue**: `cached_provider.decode('utf-8')` throws `AttributeError` because CacheService already returns decoded strings (line 26: `decode_responses=True`).

**Fix**:
```python
# Before (BROKEN):
if cached_provider.decode('utf-8') != provider:
    logger.warning(
        "oauth_csrf_provider_mismatch",
        expected_provider=cached_provider.decode('utf-8'),
        received_provider=provider
    )

# After (FIXED):
# cached_provider is already a string from CacheService
if cached_provider != provider:
    logger.warning(
        "oauth_csrf_provider_mismatch",
        expected_provider=cached_provider,
        received_provider=provider
    )
```

**Impact**: OAuth callbacks no longer crash with AttributeError.

---

### 3. ✅ Quota Update Authorization
**File**: `app/api/v1/endpoints/quota.py:73-101`

**Issue**: Any authenticated member could change organization quota limits.

**Fix**:
```python
# Added owner check before allowing quota updates
organization = orgs[0]
organization_id = organization.id

# Check if user is organization owner (only owners can update quotas)
if organization.owner_id != current_user.id:
    raise HTTPException(
        status_code=403,
        detail="Only organization owners can update quota limits"
    )
```

**Impact**: Only organization owners can update quotas, preventing privilege escalation.

---

## 🔐 Security Hardening (REQUIRES MIGRATION)

The following security improvements require database schema changes and careful migration. They are documented here for future implementation.

### 4. 🔐 TOTP Secret Encryption (RECOMMENDED)
**File**: `app/models/totp.py:34`

**Issue**: TOTP secrets stored in plaintext. If database is compromised, attackers can bypass MFA.

**Recommendation**: Encrypt TOTP secrets at rest using Fernet encryption.

**Implementation**:

1. **Created Encryption Service**: `app/core/encryption.py`
   ```python
   from cryptography.fernet import Fernet

   class EncryptionService:
       def encrypt(self, plaintext: str) -> str:
           """Encrypt using Fernet (AES-128-CBC + HMAC)"""

       def decrypt(self, ciphertext: str) -> str:
           """Decrypt encrypted data"""
   ```

2. **Migration Strategy**:
   ```python
   # In TOTPService.create_totp():
   from app.core.encryption import encryption_service

   secret = pyotp.random_base32()
   encrypted_secret = encryption_service.encrypt(secret)

   totp_secret = TOTPSecret(
       user_id=user.id,
       secret=encrypted_secret,  # Store encrypted
       ...
   )

   # When generating tokens:
   def generate_totp_token(self, secret: str) -> str:
       decrypted_secret = encryption_service.decrypt(secret)
       totp = pyotp.TOTP(decrypted_secret)
       return totp.now()
   ```

3. **Database Migration**:
   ```python
   # Alembic migration to encrypt existing secrets
   def upgrade():
       # Read all TOTP secrets
       totp_secrets = session.execute(select(TOTPSecret)).scalars().all()

       for totp in totp_secrets:
           # Encrypt plaintext secret
           totp.secret = encryption_service.encrypt(totp.secret)

       session.commit()
   ```

**Security Impact**:
- Protects MFA secrets if database is exfiltrated
- Requires `SECRET_KEY` environment variable for decryption
- Uses Fernet (AES-128-CBC + HMAC-SHA256) for authenticated encryption

**Trade-offs**:
- Small performance overhead (negligible for TOTP generation)
- Requires secure key management
- Lost `SECRET_KEY` = lost MFA secrets (document backup procedures)

---

### 5. 🔐 Token Hashing (RECOMMENDED)
**File**: `app/models/token.py:22, 58`

**Issue**: Password reset and email verification tokens stored verbatim. Database breach exposes tokens.

**Recommendation**: Store SHA-256 hash of tokens, validate by hashing submitted token.

**Implementation**:

1. **Update Token Models**:
   ```python
   class PasswordResetToken(Base):
       __tablename__ = "password_reset_tokens"

       id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
       user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
       token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # Changed from 'token'
       expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
       used: Mapped[bool] = mapped_column(Boolean, default=False)
   ```

2. **Update Token Creation**:
   ```python
   from app.core.encryption import encryption_service

   # Generate plaintext token (return to user)
   plaintext_token = PasswordResetToken.generate_token()

   # Hash token for storage
   token_hash = encryption_service.hash_token(plaintext_token)

   reset_token = PasswordResetToken(
       user_id=user.id,
       token_hash=token_hash,  # Store hash, not plaintext
       expires_at=PasswordResetToken.get_expiration()
   )

   # Return plaintext to user (only time it's visible)
   return plaintext_token
   ```

3. **Update Token Validation**:
   ```python
   async def validate_reset_token(db: AsyncSession, token: str) -> PasswordResetToken | None:
       """Validate password reset token by hashing and looking up."""
       token_hash = encryption_service.hash_token(token)

       result = await db.execute(
           select(PasswordResetToken).where(
               PasswordResetToken.token_hash == token_hash,
               PasswordResetToken.used.is_(False),
               PasswordResetToken.expires_at > datetime.now(UTC)
           )
       )
       return result.scalar_one_or_none()
   ```

4. **Database Migration**:
   ```sql
   -- Alembic migration
   ALTER TABLE password_reset_tokens RENAME COLUMN token TO token_hash;
   ALTER TABLE email_verification_tokens RENAME COLUMN token TO token_hash;

   -- NOTE: Existing tokens become invalid after migration
   -- Users must request new tokens
   ```

**Security Impact**:
- Stolen database doesn't expose active reset/verification tokens
- Replay attacks prevented if database is compromised
- Follows OWASP Token Storage Best Practices

**Trade-offs**:
- **Breaking change**: Existing tokens invalid after migration
- Users with in-flight tokens must re-request
- Slight complexity increase in token validation

---

### 6. 🔐 OAuth Token Encryption (RECOMMENDED)
**File**: `app/services/auth.py:222`

**Issue**: Third-party OAuth `access_token` and `refresh_token` stored in plaintext.

**Recommendation**: Encrypt OAuth tokens at rest.

**Implementation**:

1. **Update User Model** (if OAuth tokens stored on User):
   ```python
   class User(Base):
       # OAuth provider data (encrypted)
       oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
       oauth_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
       oauth_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Will be encrypted
       oauth_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)  # Will be encrypted
   ```

2. **Encrypt on Storage**:
   ```python
   from app.core.encryption import encryption_service

   # When storing OAuth tokens
   user.oauth_access_token = encryption_service.encrypt(access_token) if access_token else None
   user.oauth_refresh_token = encryption_service.encrypt(refresh_token) if refresh_token else None
   ```

3. **Decrypt on Use**:
   ```python
   # When using OAuth tokens
   if user.oauth_access_token:
       access_token = encryption_service.decrypt(user.oauth_access_token)
       # Use access_token to call provider API
   ```

4. **Scope Filtering** (Security Best Practice):
   ```python
   # Only request necessary OAuth scopes
   OAUTH_SCOPES = {
       "google": ["openid", "email", "profile"],  # Minimal scopes
       "github": ["read:user", "user:email"],
       # Don't request write scopes unless absolutely needed
   }
   ```

**Security Impact**:
- Protects third-party credentials if database is breached
- Limits damage from SQL injection attacks
- Follows principle of least privilege

**Trade-offs**:
- Performance overhead when refreshing OAuth tokens
- Requires secure `SECRET_KEY` management
- Increased complexity in OAuth refresh flows

---

## 📋 Implementation Checklist

### Immediate Fixes (✅ Completed)
- [x] Fix OAuth cache parameter (`ex=` → `expire=`)
- [x] Fix OAuth callback decode error
- [x] Add quota update authorization check

### Security Hardening (⏳ Planned)
- [ ] Encrypt TOTP secrets
  - [ ] Create Alembic migration
  - [ ] Update TOTPService.create_totp()
  - [ ] Update TOTPService.verify_totp()
  - [ ] Test encryption/decryption
  - [ ] Document key rotation procedures

- [ ] Hash password reset/verification tokens
  - [ ] Update token models (rename `token` → `token_hash`)
  - [ ] Create Alembic migration
  - [ ] Update token creation logic
  - [ ] Update token validation logic
  - [ ] Communicate breaking change to users

- [ ] Encrypt OAuth tokens
  - [ ] Identify where OAuth tokens are stored
  - [ ] Update storage logic to encrypt
  - [ ] Update retrieval logic to decrypt
  - [ ] Review and minimize OAuth scopes
  - [ ] Test OAuth refresh flows

---

## 🔑 Key Management

For encryption to be effective, proper key management is critical:

### Environment Variables Required

```bash
# .env
SECRET_KEY=<long-random-string-at-least-32-chars>

# For production, consider using KMS:
# AWS_KMS_KEY_ID=arn:aws:kms:...
# AZURE_KEY_VAULT_URL=https://...
```

### Key Rotation Procedure

When rotating encryption keys:

1. **Generate new key**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Dual-key decryption** (graceful migration):
   ```python
   class EncryptionService:
       def __init__(self):
           self.current_cipher = Fernet(new_key)
           self.old_cipher = Fernet(old_key)  # For decryption only

       def decrypt(self, ciphertext: str) -> str:
           try:
               return self.current_cipher.decrypt(ciphertext)
           except InvalidToken:
               # Try old key
               plaintext = self.old_cipher.decrypt(ciphertext)
               # Re-encrypt with new key
               return plaintext
   ```

3. **Re-encrypt all secrets**:
   ```python
   # Migration script
   for totp in all_totp_secrets:
       plaintext = old_cipher.decrypt(totp.secret)
       totp.secret = new_cipher.encrypt(plaintext)
   ```

---

## 🎯 Prioritization

### High Priority (Do First)
1. ✅ OAuth crash fixes (DONE - blocking production)
2. ✅ Quota authorization (DONE - privilege escalation)
3. 🔐 TOTP encryption (HIGH - MFA compromise risk)

### Medium Priority (Plan Soon)
4. 🔐 Token hashing (MEDIUM - database breach scenario)
5. 🔐 OAuth token encryption (MEDIUM - third-party credential leakage)

### Low Priority (Nice to Have)
6. OAuth scope minimization (LOW - defense in depth)
7. Key rotation automation (LOW - operational security)

---

## 📚 References

- **OWASP Cryptographic Storage Cheat Sheet**: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- **Fernet Specification**: https://github.com/fernet/spec/blob/master/Spec.md
- **NIST Key Management Guidelines**: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-57pt1r5.pdf

---

## 🧪 Testing Recommendations

Before deploying encryption changes:

1. **Unit Tests**:
   ```python
   def test_totp_encryption_roundtrip():
       secret = "JBSWY3DPEHPK3PXP"
       encrypted = encryption_service.encrypt(secret)
       decrypted = encryption_service.decrypt(encrypted)
       assert decrypted == secret
   ```

2. **Integration Tests**:
   ```python
   async def test_encrypted_totp_validation():
       # Create TOTP with encryption
       totp_secret = await TOTPService.setup_totp(...)

       # Generate token
       token = TOTPService.generate_totp_token(totp_secret.secret)

       # Validate token (requires decryption)
       is_valid = TOTPService.verify_totp_token(totp_secret, token)
       assert is_valid
   ```

3. **Load Tests**:
   - Measure encryption/decryption overhead
   - Target: <10ms overhead per TOTP verification

---

**Last Updated**: 2025-10-24
**Status**:
- ✅ Immediate fixes COMPLETE
- 🔐 Security hardening DOCUMENTED (awaiting implementation)
