-- Migration: Add automation_execution_logs table
-- This table logs automation rule executions for debugging

CREATE TABLE automation_execution_logs (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    telemetry_batch_id TEXT NOT NULL,
    rules_executed TEXT NOT NULL,  -- JSON
    commands_issued INTEGER NOT NULL DEFAULT 0,
    alerts_created INTEGER NOT NULL DEFAULT 0,
    sensor_readings TEXT NOT NULL,  -- JSON
    profile_snapshot TEXT,  -- JSON, nullable
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
);

CREATE INDEX idx_automation_logs_device ON automation_execution_logs(device_id);
CREATE INDEX idx_automation_logs_created ON automation_execution_logs(created_at);
