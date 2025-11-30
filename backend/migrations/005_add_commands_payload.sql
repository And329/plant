-- Add payload column to commands if it does not exist (for inline command data)
ALTER TABLE commands ADD COLUMN payload TEXT;
