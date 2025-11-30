-- Add message column to commands if missing
ALTER TABLE commands ADD COLUMN message TEXT;
