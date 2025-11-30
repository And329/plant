-- Migration: Change device secret from hashed to plaintext
-- Note: This migration is only needed for databases created before the initial schema
-- was updated to include the 'secret' column. New deployments can skip this.

-- This migration is a no-op for new deployments since 001_initial_schema.sql
-- already creates the devices table with the 'secret' column.

-- For existing databases (upgrade path from old schema with secret_hash):
-- Uncomment the following lines if upgrading from an old deployment:
-- ALTER TABLE devices ADD COLUMN secret TEXT;
-- ALTER TABLE devices DROP COLUMN secret_hash;

SELECT 'Migration 002: No changes needed for new deployments' AS status;
