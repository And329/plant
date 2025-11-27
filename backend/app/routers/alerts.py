from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db_session
from app.models.entities import Alert, Device
from app.schemas.alert import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Alert)
        .join(Device, Alert.device_id == Device.id)
        .where(Device.user_id == user.id)
        .order_by(Alert.created_at.desc())
    )
    alerts = result.scalars().all()
    return [AlertOut.model_validate(alert) for alert in alerts]


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
async def resolve_alert(
    alert_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Alert)
        .join(Device, Alert.device_id == Device.id)
        .where(Alert.id == alert_id, Device.user_id == user.id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")

    alert.resolved_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(alert)
    return AlertOut.model_validate(alert)

