from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActuatorType, DeviceStatus, SensorType


class DeviceCreate(BaseModel):
    name: str
    model: str | None = None
    owner_email: str | None = None
    assign_to_self: bool = True


class SensorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: SensorType
    unit: str
    calibration: dict | None = None


class ActuatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: ActuatorType
    state: str
    last_command_at: datetime | None = None


class AutomationProfileIn(BaseModel):
    soil_moisture_min: float | None = None
    soil_moisture_max: float | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    min_water_level: float | None = 20
    watering_duration_sec: int | None = 20
    watering_cooldown_min: int | None = 60
    lamp_schedule: dict | None = None


class AutomationProfileOut(AutomationProfileIn):
    id: UUID
    device_id: UUID

    model_config = ConfigDict(from_attributes=True)


class AutomationProfilePatch(BaseModel):
    soil_moisture_min: float | None = None
    soil_moisture_max: float | None = None
    temp_min: float | None = None
    temp_max: float | None = None
    min_water_level: float | None = None
    watering_duration_sec: int | None = None
    watering_cooldown_min: int | None = None
    lamp_schedule: dict | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    model: str | None
    status: DeviceStatus
    last_seen: datetime | None
    sensors: list[SensorOut] = []
    actuators: list[ActuatorOut] = []
    automation_profile: AutomationProfileOut | None = None


class DeviceProvisionResponse(BaseModel):
    device: DeviceOut
    secret: str
    sensor_ids: dict[str, str] | None = None
    actuator_ids: dict[str, str] | None = None


class DeviceConfigOut(BaseModel):
    device_id: UUID
    device_secret: str | None = None
    sensor_ids: dict[str, str]
    actuator_ids: dict[str, str]


class DeviceClaimIn(BaseModel):
    device_id: UUID
    device_secret: str
