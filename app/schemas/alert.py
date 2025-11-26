from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertSeverity, AlertType


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: AlertType
    severity: AlertSeverity
    message: str
    created_at: datetime
    resolved_at: datetime | None


class AlertCreate(BaseModel):
    type: AlertType
    severity: AlertSeverity
    message: str
