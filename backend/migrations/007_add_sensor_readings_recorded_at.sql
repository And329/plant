-- Add recorded_at column to sensor_readings if missing
ALTER TABLE sensor_readings ADD COLUMN recorded_at TIMESTAMP;
