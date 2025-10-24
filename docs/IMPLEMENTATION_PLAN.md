# Security Hardening & Feature Implementation Plan

**Date:** 2025-10-24
**Total Items:** 11
**Estimated Total Time:** 28-36 hours
**Session Target:** Complete all items

---

## EXECUTION ORDER (Priority-First)

### Phase 1: High Priority Security Hardening (8-12 hours)

#### 1. Hash Password-Reset Tokens (2-3 hours) ⏳
**Priority:** High
**Complexity:** Medium
**Breaking Change:** No (transparent to clients)

**Files to Modify:**
- `app/models/token.py` - Add token_hash field
- `app/services/token.py` - Hash on create, verify on lookup
- `app/api/v1/endpoints/auth.py` - Return token once at creation
- Migration: Add token_hash column, remove/deprecate plaintext token

**Implementation Steps:**
1. Add `token_hash` column to Token model
2. Update `create_password_reset_token()` to hash token before storage
3. Update `verify_password_reset_token()` to hash input and compare
4. Return plaintext token only once in response
5. Create migration
6. Add tests

**Dependencies:** None
**Risk:** Low - backward compatible transition possible

---

#### 2. Hash Invitation Tokens (2-3 hours) ⏳
**Priority:** High
**Complexity:** Medium
**Breaking Change:** No

**Files to Modify:**
- `app/models/invitation.py` - Add token_hash field
- `app/services/invitation_service.py` - Hash on create, verify on lookup
- `app/api/v1/endpoints/invitations.py` - Return token once
- Migration: Add token_hash column

**Implementation Steps:**
1. Add `token_hash` column to Invitation model
2. Update `create_invitation()` to hash token before storage
3. Update `accept_invitation()` to hash input and compare
4. Ensure token only returned in creation response
5. Create migration
6. Add tests

**Dependencies:** None
**Risk:** Low

---

#### 3. Encrypt TOTP Secrets (2-3 hours) ⏳
**Priority:** High
**Complexity:** Medium
**Breaking Change:** No (existing secrets need migration)

**Files to Modify:**
- `app/models/totp.py` - Update secret field handling
- `app/services/totp.py` - Encrypt/decrypt secret on read/write
- `app/core/encryption.py` - Already created, ready to use
- Migration: Encrypt existing secrets

**Implementation Steps:**
1. Update TOTPSecret model to use encrypted_secret field
2. Modify `setup_totp()` to encrypt before storage
3. Modify `verify_totp()` to decrypt before verification
4. Create migration to encrypt existing secrets
5. Add tests with encryption/decryption
6. Handle key rotation considerations

**Dependencies:** Encryption service (already exists)
**Risk:** Medium - need careful migration of existing secrets

---

#### 4. Implement MFA Login Flow (6-8 hours) ⏳
**Priority:** High
**Complexity:** High
**Breaking Change:** Yes (new login flow)

**Files to Modify:**
- `app/api/v1/endpoints/auth.py` - New two-phase login
- `app/services/auth.py` - Challenge token generation
- `app/schemas/auth.py` - New challenge response schemas
- `app/api/v1/endpoints/totp.py` - New verify endpoint for login
- Documentation: API changes

**Implementation Steps:**
1. Create challenge token system (short-lived, 5-min expiry)
2. Update `/auth/login` to check for TOTP enrollment
3. Return `requires_2fa: true` + challenge_token if enrolled
4. Create `/auth/verify-2fa` endpoint accepting challenge + TOTP
5. Issue final access/refresh tokens after TOTP verification
6. Update logout to invalidate challenge tokens
7. Add comprehensive tests
8. Update API documentation

**Dependencies:** TOTP service
**Breaking Change Details:**
- Existing clients without 2FA: No change
- Clients with 2FA: Must implement two-phase flow
- Backward compatible: Can add feature flag

**Risk:** Medium - requires client updates for 2FA users

**Reference:** Full plan in `CRITICAL_ARCHITECTURAL_FIXES.md`

---

### Phase 2: Medium Priority Features (10-14 hours)

#### 5. Integrate Session Service with OAuth (6-8 hours) ⏳
**Priority:** Medium
**Complexity:** High
**Breaking Change:** Potentially (logout behavior changes)

**Files to Modify:**
- `app/services/auth.py` - Wire to SessionService
- `app/api/v1/endpoints/auth.py` - Session creation on login
- `app/services/session.py` - Update refresh logic
- All auth flows: local, OAuth, Keycloak

**Implementation Steps:**
1. Update `authenticate_local()` to call `SessionService.create_session()`
2. Update `authenticate_oauth()` to create sessions
3. Update `authenticate_keycloak()` to create sessions
4. Update `refresh_access_token()` to validate against session table
5. Implement logout-all-devices endpoint
6. Add device fingerprinting
7. Add session management tests
8. Update documentation

**Dependencies:** Session service (exists but unused)
**Risk:** Medium - changes refresh behavior

---

#### 6. Fix Cache JSON Serialization (1-2 hours) ⏳
**Priority:** Medium
**Complexity:** Low
**Breaking Change:** No

**Files to Modify:**
- `app/services/cache.py` - Update cached decorator
- Add custom JSON encoder or switch to orjson

**Implementation Steps:**
1. Install orjson: `uv add orjson`
2. Update `cached()` decorator to use orjson
3. Add custom default handler for datetime, UUID, Pydantic
4. Test with various return types
5. Update any affected endpoints

**Dependencies:** None
**Risk:** Low - internal change only

---

#### 7. Normalize Emails to Lowercase (1-2 hours) ⏳
**Priority:** Medium
**Complexity:** Low
**Breaking Change:** No (data migration needed)

**Files to Modify:**
- `app/services/user.py` - Normalize on create/query
- `app/services/auth.py` - Normalize in auth flows
- Migration: Lowercase existing emails

**Implementation Steps:**
1. Update `create_user()` to normalize email
2. Update `get_by_email()` to normalize input
3. Update all auth flows to normalize
4. Create migration to lowercase existing emails
5. Add unique constraint on lowercase email
6. Add tests

**Dependencies:** None
**Risk:** Low - requires data migration

---

#### 8. Handle GitHub OAuth Email=None (1-2 hours) ⏳
**Priority:** Medium
**Complexity:** Medium
**Breaking Change:** No

**Files to Modify:**
- `app/services/auth.py` - Update GitHub OAuth flow
- Add GitHub email API call

**Implementation Steps:**
1. Update `get_oauth_user_info()` for GitHub
2. If email is None, call `https://api.github.com/user/emails`
3. Filter for primary, verified email
4. Fallback to first verified email
5. Return error if no verified email found
6. Add tests with mock responses

**Dependencies:** GitHub API
**Risk:** Low - enhances existing flow

---

### Phase 3: Low Priority Quality Improvements (3-7 hours)

#### 9. Populate request.state.user (30 minutes) ⏳
**Priority:** Low
**Complexity:** Very Low
**Breaking Change:** No

**Files to Modify:**
- `app/api/v1/dependencies/auth.py` - Set request.state.user

**Implementation Steps:**
1. Add `request.state.user = user` in `get_current_user()`
2. Verify logging middleware can access it
3. Test log output includes user context

**Dependencies:** None
**Risk:** None

---

#### 10. Batch Quota Commits (2-3 hours) ⏳
**Priority:** Low
**Complexity:** Medium
**Breaking Change:** No

**Files to Modify:**
- `app/services/quota.py` - Remove commits from increment methods
- All callers - Add commits after increments

**Implementation Steps:**
1. Remove `await db.commit()` from increment/decrement methods
2. Update all callers to commit after operations
3. Consider adding flush() for immediate ID generation
4. Update tests to handle commit timing
5. Document commit responsibility

**Dependencies:** None
**Risk:** Low - requires careful testing

---

#### 11. Stream File Uploads to Disk/S3 (4-6 hours) ⏳
**Priority:** Low
**Complexity:** High
**Breaking Change:** No

**Files to Modify:**
- `app/api/v1/endpoints/files.py` - Stream instead of read all
- `app/services/storage.py` - Add streaming upload
- Add python-magic for MIME detection

**Implementation Steps:**
1. Install python-magic: `uv add python-magic`
2. Update upload endpoint to stream file
3. Write to temporary file or stream to S3
4. Verify MIME type server-side
5. Compare with client content_type
6. Reject on mismatch or suspicious types
7. Add file size streaming limits
8. Add tests with large files

**Dependencies:** python-magic, libmagic
**Risk:** Medium - significant change to upload flow

---

## PROGRESS TRACKING

### ✅ Completed (0/11)
None yet

### ⏳ In Progress (0/11)
None yet

### ⏸️ Pending (11/11)
1. Hash password-reset tokens
2. Hash invitation tokens
3. Encrypt TOTP secrets
4. Implement MFA login flow
5. Integrate session service with OAuth
6. Fix cache JSON serialization
7. Normalize emails to lowercase
8. Handle GitHub OAuth email=None
9. Populate request.state.user
10. Batch quota commits
11. Stream file uploads to disk/S3

---

## MIGRATION STRATEGY

### Database Migrations Required:

1. **Token Model** - Add token_hash, migrate data
2. **Invitation Model** - Add token_hash, migrate data
3. **TOTP Model** - Encrypt existing secrets
4. **User Model** - Lowercase existing emails

### Migration Order:
1. Run all additive migrations (add columns)
2. Migrate data (hash tokens, encrypt secrets, normalize emails)
3. Deploy new code
4. Remove old columns (optional, can keep for rollback)

---

## ROLLBACK STRATEGY

### High-Risk Changes:
1. **MFA Flow** - Feature flag to disable
2. **Session Integration** - Keep JWT validation as fallback
3. **File Streaming** - Can revert to memory-based

### Low-Risk Changes:
- Token hashing: Keep plaintext as fallback during migration
- Email normalization: Reversible
- Cache serialization: Internal only

---

## TESTING STRATEGY

### Unit Tests Required:
- Token hashing/verification (both types)
- TOTP encryption/decryption
- Email normalization edge cases
- Cache serialization with various types

### Integration Tests Required:
- Full MFA login flow
- Session creation and refresh
- GitHub OAuth email fetching
- File upload streaming

### Manual Testing Recommended:
- End-to-end MFA flow
- Multi-device logout
- Large file uploads
- OAuth flows (all providers)

---

## DEPENDENCIES TO INSTALL

```bash
# Required
uv add orjson  # Cache serialization

# Optional but recommended
uv add python-magic  # MIME type detection
uv add python-magic-bin  # Windows compatibility
```

---

## ESTIMATED TIMELINE

### Aggressive (2-3 days)
- Day 1: Phase 1 (High Priority Security)
- Day 2: Phase 2 (Medium Priority Features)
- Day 3: Phase 3 (Low Priority) + Testing

### Recommended (5-7 days)
- Days 1-2: High Priority Security (with thorough testing)
- Days 3-4: Medium Priority Features
- Day 5: Low Priority Items
- Days 6-7: Integration testing and documentation

### Conservative (2 weeks)
- Week 1: High + Medium Priority
- Week 2: Low Priority + Comprehensive testing

---

## SUCCESS CRITERIA

### Phase 1 Complete:
- ✅ All tokens hashed in database
- ✅ TOTP secrets encrypted
- ✅ MFA flow working end-to-end
- ✅ All tests passing

### Phase 2 Complete:
- ✅ Session table populated for all logins
- ✅ Cache works with complex types
- ✅ No duplicate emails possible
- ✅ GitHub OAuth handles missing emails

### Phase 3 Complete:
- ✅ Request logs include user context
- ✅ Quota operations batched
- ✅ Large files stream without OOM

### Final Success:
- ✅ All 33 codex recommendations addressed
- ✅ 100% of security items complete
- ✅ Zero linting errors
- ✅ All tests passing
- ✅ Production deployment successful

---

**Next Step:** Begin Phase 1, Item 1 (Hash password-reset tokens)

**Last Updated:** 2025-10-24
