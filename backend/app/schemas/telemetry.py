from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SensorReadingIn(BaseModel):
    sensor_id: UUID
    timestamp: datetime
    value: float
    raw: dict | None = None


class TelemetryIngestRequest(BaseModel):
    readings: list[SensorReadingIn] = Field(..., min_length=1)


class TelemetryIngestResponse(BaseModel):
    batch_id: UUID
    accepted: int


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sensor_id: UUID
    recorded_at: datetime
    value_numeric: float
    raw: dict | None = None
