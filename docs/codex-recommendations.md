Critical Issues

app/api/v1/endpoints/stripe_webhooks.py:64 The duplicate-event guard queries the BillingService class, which makes SQLAlchemy raise and aborts every webhook; switch the lookup to BillingEvent so idempotent processing works.
app/api/v1/endpoints/files.py:193 Using not FileModel.is_deleted (and similar in this module) triggers SQLAlchemy’s “Boolean value of this clause is not defined”; replace with FileModel.is_deleted.is_(False) so file listings and counts no longer crash.
app/api/v1/endpoints/totp.py:42 After TOTPService.setup_totp hashes the original backup codes, the endpoint generates a fresh set, meaning users receive codes that will never validate; have the service return the plaintext codes once and return those to the client.
app/services/session.py:105 Refresh-token lookups re-hash the presented token and use not UserSession.revoked, so comparisons always miss and SQLAlchemy raises; use verify_password(refresh_token, session.token_hash) and column .is_(False) checks to make session management workable.
High Priority

app/services/notification_service.py:120 and app/services/invitation_service.py:66 Both services rely on ... is False, which evaluates to False immediately and empties every query; change these filters to .is_(False) to restore unread/pending behaviours.
app/api/v1/endpoints/webhooks.py:43 Several endpoints assume current_user.organization_id, but User instances don’t expose that attribute, so every call returns 400; populate an “active organization” in the auth dependency (e.g. first membership) or require it explicitly in the route.
app/tasks/email.py:59 Building links with settings.CORS_ORIGINS[0] breaks when the env var is the default comma-separated string; use settings.get_cors_origins()[0] (or another canonical base URL) so verification/reset emails point to real pages.
Security / Best Practices

app/schemas/webhook.py:36 Every webhook response exposes the full signing secret; restrict the raw secret to creation time and return masked values afterwards to avoid credential leakage inside the tenant.
app/api/v1/endpoints/files.py:69 File uploads read the entire body into memory and trust the client’s content_type; consider streaming to disk/S3 and verifying MIME types server-side (e.g. python-magic) to resist large-file DoS and disguised executables.
Next steps: 1. Patch the failing ORM predicates (not/is False) and add regression tests covering list notifications/invitations, file pagination, and session lookups. 2. Refactor TOTP setup to surface the original backup codes once, with tests ensuring those codes validate. 3. Update webhook/email handling (secret masking, base URL resolution) and add integration tests for webhook idempotency and email-link generation.



More Blocking Issues

app/api/v1/endpoints/auth.py:220 – cache.set(..., ex=600) passes an unsupported kwarg; FastAPI returns 500 before the user even hits the provider. Switch to the existing expire= parameter or extend CacheService.set to accept ex.
app/api/v1/endpoints/auth.py:284 – cached_provider is already a str (see app/services/cache.py:40-42), so calling .decode("utf-8") throws AttributeError, breaking every OAuth callback. Compare directly against the string and log it safely.
Security Gaps to Close

app/api/v1/endpoints/quota.py:73 still allows any authenticated member to change organization quota limits; add an explicit owner/admin check before updates go through.
app/models/totp.py:34 keeps the TOTP secret in plaintext despite the “encrypted in production” comment—wrap this in envelope encryption (KMS or libsodium) so leaked DBs don’t expose MFA seeds.
app/models/token.py:22 persists password-reset and verification tokens verbatim. Hashing those tokens (store digest, compare on lookup) blocks replay if the table is exfiltrated.
app/services/auth.py:222 saves third-party access_token/refresh_token blobs without encryption or scope filtering; encrypt at rest and consider trimming to the fields you actually need.
Feature / Hardening Ideas

Wire OAuth sign-in to the session store so refresh-token revocation actually logs users out across devices (coordinate AuthService.refresh_access_token with SessionService).
Add an explicit “active organization” selector (e.g., persisted in request.state) so multi-tenant routes stop relying on a missing current_user.organization_id.
Surface admin tooling for API/webhook secrets rotation and audit logging—issue short-lived presigned views and enforce re-verification when secrets are regenerated.


More Findings

Dead-letter queue endpoints (app/api/v1/endpoints/dead_letter.py:20, :33, :55, :74, :95, :113) accept any authenticated user and even let callers supply resolved_by (app/schemas/dead_letter.py:33), so regular members can hide or “resolve” background-job failures. Restrict these routes to superusers and derive resolved_by from current_user.
Several routes (for example app/api/v1/endpoints/webhooks.py:43 and app/api/v1/dependencies/quota.py:31) rely on current_user.organization_id, but the ORM model in app/models/user.py exposes only the organizations relationship—no scalar attribute exists—so these endpoints raise AttributeError as soon as they’re hit. Add an “active organization” field in the auth dependency (or require it explicitly from the client) before keeping that contract.
OAuth/Keycloak sign-ups (app/services/auth.py:204 and :287) create the user but never attach them to the default organization, so downstream checks like quota enforcement or webhook management immediately fail. Reuse the same OrganizationService.get_or_create_default + add_member flow used in the email/password registration path.
Local authentication (app/services/auth.py:22) does not gate on user.is_verified and never enforces a TOTP challenge even when users have 2FA enabled, so unverified or unenrolled sessions receive full tokens. Add the verification check and prompt for a second factor before minting tokens.
The session subsystem is effectively inert: tokens are issued in authenticate_local / authenticate_oauth without calling SessionService.create_session, refresh_access_token (app/services/auth.py:53) honors any valid JWT without touching the DB, and the session table therefore never records or revokes refresh tokens. Wire the auth flows through the session service (and make refresh consult it) so logout-all-devices, revocation, and device tracking actually work.
Quality / Hardening Opportunities

Populate request.state.user inside get_current_user (app/api/v1/dependencies/auth.py:25) so the logging middleware at app/middleware/logging.py:31 can emit user context as intended.
Normalize emails to lowercase when creating or querying users (app/services/user.py:26, :55, app/services/auth.py:204) to avoid duplicate accounts differing only by case.
GitHub OAuth often returns email=None; extend AuthService.get_oauth_user_info (app/services/auth.py:118) to hit /user/emails and pick the primary verified address.
The usage-quota helpers (app/services/quota.py:228, :247, :266) commit on every counter increment. Consider batching or moving the commit responsibility up to the caller to cut transaction chatter under load.
Feature Ideas

Persist an “active organization” choice per user (API + UI) so multi-tenant routes don’t assume a single-org membership.
Add a true MFA login flow: issue a short-lived challenge token from /auth/login, require /totp/verify before minting long-lived access/refresh tokens, and expire those when the user disables 2FA.
Expose admin tooling to rotate API/webhook secrets, audit past values, and force downstream re-verification to keep integrations from staling.

More Issues To Address

app/api/v1/endpoints/users.py:83 returns any user record to any authenticated caller. For multi-tenant isolation you should require either superuser status or shared-organization membership before exposing another user’s profile.
app/api/v1/dependencies/quota.py:15 et al. define quota guards, but no endpoint actually includes them as dependencies. As a result, API, storage, and user limits are never enforced; wire them into upload/user-creation routes and log the usage counters in the happy path.
app/api/v1/endpoints/dead_letter.py:20 allows any logged-in member to read or “resolve” dead-letter tasks and even supply an arbitrary resolved_by value. Restrict these endpoints to superusers and derive the resolver from current_user.
app/services/auth.py:204 (OAuth) creates users without adding them to the default organization, so downstream flows that expect current_user to have an active org fail immediately. Reuse the default-org + membership bootstrap used in email/password registration.
app/services/auth.py:53 refreshes tokens without checking UserService.is_locked or is_verified, so locked or unverified accounts can keep minting new tokens as long as they hold a refresh token. Reapply the same gating logic you have in the login path.
Extra Hardening Ideas

Normalize and index email addresses in lowercase inside UserService to avoid duplicate accounts that differ only by case.
Populate request.state.user inside get_current_user so the logging middleware can bind a user ID to every request log entry.
Implement an explicit “active organization” concept (persisted per user or passed via header) and set it during auth; many endpoints currently assume current_user.organization_id exists even though the model doesn’t expose it.
After hooking quota dependencies, extend the quota service to record which endpoint consumed the allowance and surface those stats in the admin UI or billing dashboards.


app/api/v1/endpoints/users.py:83 lets any authenticated user pull full profiles for arbitrary user IDs. Lock this route down to superusers or members of the same organization before you leak tenant data across accounts.

app/api/v1/dependencies/quota.py:15 defines quota guards, but none of the upload, user-creation, or billing endpoints depend on them. Until you wire these dependencies in, API-call and storage limits never trigger and the quota tables drift from reality.

app/services/invitation_service.py:70 stores invitation tokens in plaintext and /api/v1/invitations/... responses expose freshly-minted tokens. Treat them like password-reset secrets—hash them in the database and return them only once over a secure channel.

app/services/auth.py:204 creates OAuth/Keycloak sign-ups without adding them to the default organization. Those users hit immediate 403/400 errors anywhere the code expects membership (quotas, webhooks, teams). Reuse the same default-org bootstrap you run for email/password registrations.

app/services/cache.cached serializes results with json.dumps; any endpoint returning datetimes, UUIDs, or Pydantic models will explode the first time the decorator is used. Either drop to orjson with a custom encoder or let the decorator accept non-JSON-safe types.

Let me know if you’d like help patching any of these.