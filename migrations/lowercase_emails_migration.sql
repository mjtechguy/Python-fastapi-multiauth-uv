-- Migration: Normalize existing user emails to lowercase
-- Date: 2025-10-24
-- Description: Updates all user emails to lowercase to prevent duplicate accounts

-- IMPORTANT: Run this migration during a maintenance window to avoid conflicts

BEGIN;

-- Step 1: Update all user emails to lowercase
UPDATE users
SET email = LOWER(TRIM(email))
WHERE email != LOWER(TRIM(email));

-- Step 2: Check for potential duplicates after normalization
-- Run this query BEFORE committing to identify any conflicts
SELECT
    LOWER(TRIM(email)) as normalized_email,
    COUNT(*) as count,
    STRING_AGG(id::text, ', ') as user_ids
FROM users
GROUP BY LOWER(TRIM(email))
HAVING COUNT(*) > 1;

-- If duplicates exist, you need to manually resolve them before proceeding
-- Options:
-- 1. Merge accounts (requires custom logic)
-- 2. Delete/deactivate duplicate accounts
-- 3. Suffix email addresses (e.g., user+1@example.com)

-- Step 3: After resolving duplicates, add a unique constraint on lowercase email
-- CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lower
--     ON users (LOWER(TRIM(email)));

COMMIT;

-- Verification query - should return 0 rows
SELECT email, COUNT(*)
FROM users
GROUP BY LOWER(TRIM(email))
HAVING COUNT(*) > 1;
