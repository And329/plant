-- Add value_numeric column to sensor_readings if missing
ALTER TABLE sensor_readings ADD COLUMN value_numeric REAL;
