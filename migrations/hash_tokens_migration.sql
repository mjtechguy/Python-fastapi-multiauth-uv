-- Migration: Hash password reset and email verification tokens
-- Date: 2025-10-24
-- Description: Adds token_hash column and migrates existing tokens

-- IMPORTANT: This is a breaking migration that will invalidate all existing tokens
-- Users with pending password resets or email verifications will need to request new ones

BEGIN;

-- Step 1: Add token_hash columns to both tables
ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS token_hash VARCHAR(64);
ALTER TABLE email_verification_tokens ADD COLUMN IF NOT EXISTS token_hash VARCHAR(64);

-- Step 2: Create unique indexes on token_hash
CREATE UNIQUE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash
    ON password_reset_tokens (token_hash);
CREATE UNIQUE INDEX IF NOT EXISTS idx_email_verification_tokens_token_hash
    ON email_verification_tokens (token_hash);

-- Step 3: OPTION A - Mark all existing tokens as used (safest approach)
-- This invalidates all pending tokens and users must request new ones
UPDATE password_reset_tokens SET used = true WHERE token_hash IS NULL;
UPDATE email_verification_tokens SET used = true WHERE token_hash IS NULL;

-- Step 3: OPTION B - Delete all existing tokens (alternative)
-- Uncomment below if you prefer to delete instead of marking as used
-- DELETE FROM password_reset_tokens WHERE token_hash IS NULL;
-- DELETE FROM email_verification_tokens WHERE token_hash IS NULL;

-- Step 4: Drop the old token column (optional, can keep for rollback)
-- IMPORTANT: Only do this after verifying the new system works
-- ALTER TABLE password_reset_tokens DROP COLUMN IF EXISTS token;
-- ALTER TABLE email_verification_tokens DROP COLUMN IF EXISTS token;

-- Step 5: Make token_hash NOT NULL (optional, after old tokens removed)
-- ALTER TABLE password_reset_tokens ALTER COLUMN token_hash SET NOT NULL;
-- ALTER TABLE email_verification_tokens ALTER COLUMN token_hash SET NOT NULL;

COMMIT;

-- Verification queries
SELECT 'password_reset_tokens' as table_name, COUNT(*) as total,
       SUM(CASE WHEN token_hash IS NOT NULL THEN 1 ELSE 0 END) as with_hash
FROM password_reset_tokens;

SELECT 'email_verification_tokens' as table_name, COUNT(*) as total,
       SUM(CASE WHEN token_hash IS NOT NULL THEN 1 ELSE 0 END) as with_hash
FROM email_verification_tokens;

-- Notes:
-- 1. All users with pending password resets will need to request a new reset link
-- 2. All users with pending email verifications will need to request a new verification email
-- 3. This is necessary for security - tokens are now hashed and cannot be recovered
-- 4. Consider sending a notification to affected users
