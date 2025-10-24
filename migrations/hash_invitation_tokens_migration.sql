-- Migration: Hash invitation tokens
-- Date: 2025-10-24
-- Description: Adds token_hash column and migrates existing invitation tokens

-- IMPORTANT: This is a breaking migration that will invalidate all existing invitations
-- Users with pending invitations will need to be re-invited

BEGIN;

-- Step 1: Add token_hash column
ALTER TABLE invitations ADD COLUMN IF NOT EXISTS token_hash VARCHAR(64);

-- Step 2: Create unique index on token_hash
CREATE UNIQUE INDEX IF NOT EXISTS idx_invitations_token_hash
    ON invitations (token_hash);

-- Step 3: OPTION A - Mark all existing invitations as expired (safest approach)
-- This invalidates all pending invitations and users must be re-invited
UPDATE invitations
SET expires_at = NOW() - INTERVAL '1 day'
WHERE token_hash IS NULL AND is_accepted = false;

-- Step 3: OPTION B - Delete all existing invitations (alternative)
-- Uncomment below if you prefer to delete instead of expiring
-- DELETE FROM invitations WHERE token_hash IS NULL AND is_accepted = false;

-- Step 4: Drop the old token column (optional, can keep for rollback)
-- IMPORTANT: Only do this after verifying the new system works
-- ALTER TABLE invitations DROP COLUMN IF EXISTS token;

-- Step 5: Make token_hash NOT NULL (optional, after old tokens removed)
-- ALTER TABLE invitations ALTER COLUMN token_hash SET NOT NULL;

COMMIT;

-- Verification queries
SELECT 'invitations' as table_name, COUNT(*) as total,
       SUM(CASE WHEN token_hash IS NOT NULL THEN 1 ELSE 0 END) as with_hash,
       SUM(CASE WHEN is_accepted = false AND expires_at > NOW() THEN 1 ELSE 0 END) as pending_valid
FROM invitations;

-- Notes:
-- 1. All users with pending invitations will need to be re-invited
-- 2. This is necessary for security - invitation tokens are now hashed and cannot be recovered
-- 3. Consider notifying organization owners to re-invite pending users
-- 4. Accepted invitations are not affected
