from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CommandStatus, CommandType


class DeviceCommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    command: CommandType
    payload: dict | None
    actuator_id: UUID | None
    created_at: datetime


class CommandAckIn(BaseModel):
    command_id: UUID
    status: CommandStatus = CommandStatus.ACKED
    feedback: dict | None = None


class CommandStatusResponse(BaseModel):
    id: UUID
    status: CommandStatus
    message: str | None = None


class CommandCreateIn(BaseModel):
    actuator_id: UUID
    command: CommandType
    payload: dict | None = None


class CommandCreateResponse(DeviceCommandOut):
    status: CommandStatus
