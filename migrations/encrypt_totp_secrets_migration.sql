-- Migration: Encrypt TOTP secrets
-- Date: 2025-10-24
-- Description: Adds encrypted_secret column and migrates from plaintext secret field

-- IMPORTANT: This is a breaking migration that will invalidate all existing TOTP secrets
-- Users with TOTP enabled will need to re-setup their 2FA

BEGIN;

-- Step 1: Add encrypted_secret column
ALTER TABLE totp_secrets ADD COLUMN IF NOT EXISTS encrypted_secret VARCHAR(255);

-- Step 2: OPTION A - Disable all existing TOTP (safest approach)
-- This forces all users to re-setup TOTP with encrypted secrets
UPDATE totp_secrets
SET is_enabled = false,
    is_verified = false
WHERE encrypted_secret IS NULL;

-- Step 2: OPTION B - Delete all existing TOTP secrets (alternative)
-- Uncomment below if you prefer to delete instead of disabling
-- DELETE FROM totp_secrets WHERE encrypted_secret IS NULL;

-- Step 3: Drop the old secret column (optional, can keep for rollback)
-- IMPORTANT: Only do this after verifying the new system works
-- ALTER TABLE totp_secrets DROP COLUMN IF EXISTS secret;

-- Step 4: Make encrypted_secret NOT NULL (optional, after old secrets removed)
-- ALTER TABLE totp_secrets ALTER COLUMN encrypted_secret SET NOT NULL;

COMMIT;

-- Verification queries
SELECT 'totp_secrets' as table_name, COUNT(*) as total,
       SUM(CASE WHEN encrypted_secret IS NOT NULL THEN 1 ELSE 0 END) as with_encryption,
       SUM(CASE WHEN is_enabled = true THEN 1 ELSE 0 END) as enabled
FROM totp_secrets;

-- Notes:
-- 1. All users with TOTP enabled will need to re-setup their 2FA
-- 2. This is necessary for security - TOTP secrets must be encrypted at rest
-- 3. Consider notifying users to re-enable 2FA after migration
-- 4. The new system uses Fernet encryption (AES-128-CBC + HMAC-SHA256)
-- 5. Backup codes remain hashed with bcrypt and are not affected
