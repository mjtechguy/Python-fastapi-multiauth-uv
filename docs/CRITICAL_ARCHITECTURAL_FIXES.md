# Critical Architectural Fixes Required

**Date**: 2025-10-24
**Priority**: 🔴 CRITICAL - Multiple endpoints will crash in production

---

## Overview

This document outlines critical architectural issues discovered during code review. These issues will cause immediate crashes or security breaches in production and require systematic fixes across the codebase.

---

## 🔴 CRITICAL: Organization ID Access Pattern (BREAKS MANY ENDPOINTS)

### Issue

**Severity**: CRITICAL - Will crash webhooks, quota checks, and many other endpoints

**Root Cause**: Code assumes `current_user.organization_id` exists, but the ORM model only has `organizations` (list relationship).

**Affected Files**:
- `app/api/v1/dependencies/quota.py` (lines 31, 34, 68, 71, 113, 116)
- `app/api/v1/endpoints/webhooks.py` (line 43) - Already fixed with helper
- Any endpoint that uses `current_user.organization_id`

**Current Behavior**: `AttributeError: 'User' object has no attribute 'organization_id'`

### Solution Implemented

Created helper function in `app/api/v1/endpoints/webhooks.py:28`:

```python
def get_user_organization_id(user: User) -> uuid.UUID:
    """Get organization ID from user's first organization."""
    if not user.organizations:
        raise HTTPException(status_code=400, detail="User does not belong to an organization")
    return user.organizations[0].id
```

### Required Actions

1. **Move helper to shared location**:
   ```python
   # Create: app/core/organization_helpers.py
   from fastapi import HTTPException
   import uuid
   from app.models.user import User

   def get_user_organization_id(user: User) -> uuid.UUID:
       """
       Get organization ID from user's first organization.

       For single-org membership model, returns the user's only organization.
       For global admins, returns their first organization.

       Raises:
           HTTPException: If user doesn't belong to any organization
       """
       if not user.organizations:
           raise HTTPException(
               status_code=400,
               detail="User does not belong to an organization"
           )
       return user.organizations[0].id
   ```

2. **Fix quota dependencies**:
   ```python
   # app/api/v1/dependencies/quota.py
   from app.core.organization_helpers import get_user_organization_id

   async def check_api_quota(current_user: Annotated[User, Depends(get_current_user)]):
       # Before (BROKEN):
       # if not hasattr(current_user, 'organization_id') or not current_user.organization_id:
       #     raise HTTPException(...)
       # organization_id = current_user.organization_id

       # After (FIXED):
       organization_id = get_user_organization_id(current_user)
   ```

3. **Search and replace across codebase**:
   ```bash
   # Find all usages:
   grep -r "current_user\.organization_id" app/

   # Replace with:
   organization_id = get_user_organization_id(current_user)
   ```

---

## 🔴 CRITICAL: OAuth/Keycloak Users Not Added to Default Organization

### Issue

**Severity**: CRITICAL - OAuth users cannot use quota, webhooks, or any org-scoped features

**Root Cause**: `authenticate_oauth()` and `authenticate_keycloak()` create users but never add them to default organization.

**Affected Files**:
- `app/services/auth.py:204` (OAuth)
- `app/services/auth.py:287` (Keycloak)

**Current Behavior**:
1. User signs in with OAuth/Keycloak
2. User created successfully
3. User has NO organizations
4. Quota checks fail → 400 error
5. Webhook management fails → 400 error
6. Any org-scoped feature fails

### Solution

**File**: `app/services/auth.py`

```python
@staticmethod
async def authenticate_oauth(
    db: AsyncSession, provider: str, code: str
) -> tuple[User, bool]:
    """Authenticate user via OAuth, create if needed."""
    # ... existing code to get user_info ...

    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        # Existing user - just return
        await db.commit()
        return user, False

    # Create new user
    new_user = User(
        email=email,
        username=username,
        full_name=full_name,
        is_active=True,
        is_verified=True,  # OAuth providers verify emails
    )
    db.add(new_user)
    await db.flush()  # Get user.id

    # Create OAuth account link
    oauth_account = OAuthAccount(
        user_id=new_user.id,
        provider=provider,
        provider_user_id=provider_user_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(oauth_account)

    # ✅ FIX: Add to default organization (same as email/password registration)
    from app.services.organization import OrganizationService

    default_org = await OrganizationService.get_or_create_default_organization(db)
    await OrganizationService.add_member(db, default_org.id, new_user.id)

    await db.commit()
    await db.refresh(new_user)

    return new_user, True
```

**Apply same fix to `authenticate_keycloak()` at line 287.**

---

## 🔴 CRITICAL: Local Auth Missing Email Verification Check

### Issue

**Severity**: HIGH - Unverified users can access the system

**Root Cause**: `authenticate_local()` doesn't check `user.is_verified`

**Affected File**: `app/services/auth.py:22`

**Current Behavior**: Users can login immediately after registration, even without verifying email.

### Solution

```python
@staticmethod
async def authenticate_local(
    db: AsyncSession, email: str, password: str
) -> User:
    """Authenticate user with email and password."""
    from app.core.security import verify_password

    # Get user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("Invalid email or password")

    # ✅ FIX: Check email verification
    if not user.is_verified:
        raise ValueError("Email not verified. Please check your inbox.")

    # Check password
    if not user.hashed_password or not verify_password(password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        # ... rest of lockout logic ...
        raise ValueError("Invalid email or password")

    # ... rest of method ...
```

---

## 🔴 CRITICAL: Local Auth Missing TOTP Challenge

### Issue

**Severity**: HIGH - 2FA can be bypassed

**Root Cause**: `authenticate_local()` returns tokens immediately, even for users with TOTP enabled.

**Affected File**: `app/services/auth.py:22`

**Current Behavior**:
1. User enables TOTP
2. User logs in with password
3. Gets full access tokens immediately
4. **TOTP never checked**

### Solution

This requires a two-phase login flow:

**Phase 1**: Create intermediate token after password validation

```python
# app/schemas/auth.py
class LoginResponse(BaseModel):
    """Response from login endpoint."""
    requires_2fa: bool = False
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
```

**Phase 2**: Update login endpoint

```python
# app/api/v1/endpoints/auth.py
@router.post("/login", response_model=LoginResponse)
async def login(...):
    """Login with email/password."""
    # Authenticate with password
    user = await AuthService.authenticate_local(db, credentials.email, credentials.password)

    # ✅ FIX: Check if 2FA is enabled
    if user.totp_secret and user.totp_secret.is_enabled:
        # User has 2FA enabled - don't issue tokens yet
        # Create short-lived challenge token
        challenge_token = create_2fa_challenge_token(user.id)
        await cache.set(
            f"2fa_challenge:{user.id}",
            challenge_token,
            expire=300  # 5 minutes
        )

        return LoginResponse(
            requires_2fa=True,
            access_token=None,
            refresh_token=None
        )

    # No 2FA - issue tokens directly
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(db, user.id)

    return LoginResponse(
        requires_2fa=False,
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
```

**Phase 3**: Add TOTP verification endpoint

```python
@router.post("/verify-2fa", response_model=Token)
async def verify_2fa(
    request: Verify2FARequest,  # Contains: user_id, totp_token
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Verify TOTP and issue tokens."""
    # Verify challenge token exists
    challenge = await cache.get(f"2fa_challenge:{request.user_id}")
    if not challenge:
        raise HTTPException(status_code=400, detail="No active 2FA challenge")

    # Get user and TOTP secret
    user = await db.get(User, request.user_id)
    if not user or not user.totp_secret:
        raise HTTPException(status_code=400, detail="Invalid request")

    # Verify TOTP token
    is_valid = TOTPService.verify_totp_token(user.totp_secret, request.totp_token)
    if not is_valid:
        # Try backup codes
        is_valid = TOTPService.verify_backup_code(user.totp_secret, request.totp_token)

    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid TOTP code")

    # Clear challenge
    await cache.delete(f"2fa_challenge:{request.user_id}")

    # Issue tokens
    access_token = create_access_token(user.id)
    refresh_token = await create_refresh_token(db, user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )
```

---

## 🔴 CRITICAL: Session Service Not Wired to Auth Flows

### Issue

**Severity**: HIGH - Session management completely broken

**Root Cause**: Tokens issued without calling `SessionService.create_session()`, refresh doesn't consult DB.

**Affected Files**:
- `app/services/auth.py:22` (`authenticate_local`)
- `app/services/auth.py:53` (`refresh_access_token`)
- `app/services/auth.py:131` (`authenticate_oauth`)
- `app/services/auth.py:214` (`authenticate_keycloak`)

**Current Behavior**:
- Sessions table is never populated
- "Logout all devices" doesn't work
- Session revocation doesn't work
- Device tracking doesn't work
- Refresh tokens aren't stored or validated

### Solution

**Update token creation to use sessions**:

```python
# app/services/auth.py
async def create_tokens_with_session(
    db: AsyncSession,
    user: User,
    ip_address: str,
    user_agent: str,
    device_info: str | None = None
) -> tuple[str, str]:
    """Create access and refresh tokens with session tracking."""
    from app.services.session import SessionService

    # Create access token (JWT)
    access_token = create_access_token(user.id)

    # Create session with refresh token
    session = await SessionService.create_session(
        db,
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        device_info=device_info
    )

    # The refresh token is stored in session.token_hash
    # Return the plaintext refresh token
    return access_token, session.id.hex  # Use session ID as refresh token
```

**Update refresh endpoint**:

```python
@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Refresh access token using refresh token (session ID)."""
    from app.services.session import SessionService

    # Get session by token (this validates it's not revoked/expired)
    session = await SessionService.get_session_by_token(db, request.refresh_token)

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Create new access token
    access_token = create_access_token(session.user_id)

    # Optionally rotate refresh token
    # new_refresh_token = await SessionService.rotate_token(db, session.id)

    return Token(
        access_token=access_token,
        refresh_token=request.refresh_token,  # Or new_refresh_token if rotating
        token_type="bearer"
    )
```

---

## 🔴 CRITICAL: Dead Letter Queue Authorization

### Issue

**Severity**: MEDIUM - Regular users can hide background job failures

**Root Cause**: DLQ endpoints accept any authenticated user, allow arbitrary `resolved_by`

**Affected File**: `app/api/v1/endpoints/dead_letter.py` (all endpoints)

**Current Behavior**: Any authenticated user can resolve, retry, or hide DLQ entries.

### Solution

```python
# app/api/v1/endpoints/dead_letter.py

from app.api/v1.dependencies.auth import get_current_superuser

# Change all endpoints from:
# current_user: Annotated[User, Depends(get_current_user)]

# To:
# current_user: Annotated[User, Depends(get_current_superuser)]

# And in schemas:
class ResolveTaskRequest(BaseModel):
    """Request to resolve a dead letter task."""
    reason: str | None = None
    # ✅ REMOVED: resolved_by field (derive from current_user)

# In endpoint:
@router.post("/{task_id}/resolve", response_model=DeadLetterTaskResponse)
async def resolve_task(
    task_id: uuid.UUID,
    request: ResolveTaskRequest,
    current_user: Annotated[User, Depends(get_current_superuser)],  # ✅ superuser only
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Resolve a dead letter task (superuser only)."""
    await DeadLetterService.resolve_task(
        db,
        task_id=task_id,
        resolved_by=current_user.id,  # ✅ derive from current_user
        reason=request.reason
    )
```

---

## Implementation Priority

### Phase 1: Immediate Fixes (Will Crash in Production)
1. ✅ Organization ID helper function (move to shared location)
2. ✅ Fix quota dependencies to use helper
3. ✅ Fix OAuth/Keycloak default organization assignment
4. ✅ Add email verification check to local auth

### Phase 2: Security Fixes (Can Be Bypassed)
5. ⏳ Implement 2FA challenge flow
6. ⏳ Wire session service into auth flows
7. ⏳ Fix DLQ authorization

### Phase 3: Quality Improvements (Non-Breaking)
8. ⏳ Populate `request.state.user` in dependency
9. ⏳ Normalize emails to lowercase
10. ⏳ Fix GitHub OAuth email=None handling
11. ⏳ Batch quota counter commits

---

## Testing Requirements

After fixes, test:

1. **Organization Access**:
   - Quota enforcement works for all users
   - Webhook management works
   - OAuth users can access org-scoped features

2. **Email Verification**:
   - Unverified users cannot login
   - Verified users can login normally

3. **2FA Flow**:
   - Password correct → 2FA challenge
   - Valid TOTP → tokens issued
   - Invalid TOTP → denied
   - Backup codes work

4. **Session Management**:
   - Logout all devices works
   - Revoked sessions cannot refresh
   - Sessions table populates correctly

5. **DLQ Authorization**:
   - Regular users get 403
   - Superusers can manage DLQ
   - resolved_by is always current user

---

## Migration Impact

### Breaking Changes
- **2FA Flow**: Clients must handle `requires_2fa` response
- **Email Verification**: Unverified users blocked (intentional)
- **DLQ Access**: Regular users lose access (intentional)

### Database Changes
- None required (all logic changes)

### API Changes
- Login response adds `requires_2fa` field
- New `/verify-2fa` endpoint required
- DLQ endpoints require superuser token

---

**Last Updated**: 2025-10-24
**Status**: 🔴 CRITICAL FIXES REQUIRED
**Estimated Effort**: 8-16 hours
**Risk**: HIGH - Production will crash without Phase 1 fixes
