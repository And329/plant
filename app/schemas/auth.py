from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserOut


class DeviceAuthRequest(BaseModel):
    device_id: UUID = Field(..., description="Provisioned device identifier")
    device_secret: str = Field(..., min_length=8)
    firmware_version: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class DeviceTokenResponse(TokenPair):
    pass


class RefreshRequest(BaseModel):
    refresh_token: str


class ProvisionedDevice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class DeviceAuthResponse(DeviceTokenResponse):
    device: ProvisionedDevice
    automation_profile: dict | None = None


class UserTokenResponse(TokenPair):
    user: UserOut
