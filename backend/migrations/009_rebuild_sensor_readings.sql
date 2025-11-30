-- Rebuild sensor_readings to match current model (recorded_at, value_numeric, raw)
PRAGMA foreign_keys=off;

CREATE TABLE IF NOT EXISTS sensor_readings_new (
    id TEXT PRIMARY KEY,
    sensor_id TEXT NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    value_numeric REAL,
    raw TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
);

INSERT INTO sensor_readings_new (id, sensor_id, recorded_at, value_numeric, raw, created_at, updated_at)
SELECT
    id,
    sensor_id,
    COALESCE(recorded_at, timestamp, CURRENT_TIMESTAMP),
    COALESCE(value_numeric, value),
    raw,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
FROM sensor_readings;

DROP TABLE sensor_readings;
ALTER TABLE sensor_readings_new RENAME TO sensor_readings;

CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor_id ON sensor_readings(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_recorded_at ON sensor_readings(recorded_at);

PRAGMA foreign_keys=on;
