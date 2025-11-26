from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DeviceStatus, SensorType


class DeviceCreate(BaseModel):
    name: str
    model: str | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    model: str | None
    status: DeviceStatus
    last_seen: datetime | None


class SensorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: SensorType
    unit: str
    calibration: dict | None = None


class AutomationProfileIn(BaseModel):
    soil_moisture_min: float = Field(..., gt=0)
    soil_moisture_max: float = Field(..., gt=0)
    temp_min: float
    temp_max: float
    min_water_level: float = 20
    watering_duration_sec: int = 20
    watering_cooldown_min: int = 60
    lamp_schedule: dict | None = None


class AutomationProfileOut(AutomationProfileIn):
    id: UUID
    device_id: UUID

    model_config = ConfigDict(from_attributes=True)


class DeviceProvisionResponse(BaseModel):
    device: DeviceOut
    secret: str
