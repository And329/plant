-- Migration: Change device secret from hashed to plaintext
-- This migration adds a 'secret' column and removes 'secret_hash'

-- Step 1: Add new secret column (nullable initially)
ALTER TABLE devices ADD COLUMN secret TEXT;

-- Step 2: For existing devices, generate new secrets (since we can't unhash)
-- In production, you'd want to notify admins to re-provision devices
-- For now, we'll just set a placeholder that indicates re-provisioning needed

-- Step 3: Drop the old secret_hash column
ALTER TABLE devices DROP COLUMN secret_hash;

-- Note: Existing unclaimed devices will need to be re-provisioned with new secrets
-- Claimed devices don't need secrets anymore (they're already linked to users)
