from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_automation_engine, get_current_device, get_current_user, get_db_session
from app.models.entities import Device, Sensor, SensorReading
from app.schemas.telemetry import TelemetryIngestRequest, TelemetryIngestResponse
from app.services.automation_engine import AutomationEngine, TelemetryRecord

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("", response_model=TelemetryIngestResponse)
async def ingest_telemetry(
    payload: TelemetryIngestRequest,
    device=Depends(get_current_device),
    session: AsyncSession = Depends(get_db_session),
    automation: AutomationEngine = Depends(get_automation_engine),
):
    sensor_ids = {reading.sensor_id for reading in payload.readings}
    result = await session.execute(
        select(Sensor).where(Sensor.id.in_(sensor_ids), Sensor.device_id == device.id)
    )
    sensors = {sensor.id: sensor for sensor in result.scalars().all()}
    if len(sensors) != len(sensor_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown sensor")

    readings = []
    for reading in payload.readings:
        entity = SensorReading(
            sensor_id=reading.sensor_id,
            recorded_at=reading.timestamp,
            value_numeric=reading.value,
            raw=reading.raw,
        )
        readings.append(entity)
        session.add(entity)

    await session.commit()
    batch_id = uuid4()
    await automation.enqueue(
        str(device.id),
        str(batch_id),
        [TelemetryRecord(sensor_id=str(r.sensor_id), value=r.value_numeric, timestamp=r.recorded_at) for r in readings],
    )

    return TelemetryIngestResponse(batch_id=batch_id, accepted=len(readings))


@router.get("/latest/{device_id}")
async def get_latest_readings(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Get latest sensor readings for a device."""
    # Verify device belongs to user
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.sensors))
        .where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # Get latest reading for each sensor
    readings = []
    for sensor in device.sensors:
        reading_result = await session.execute(
            select(SensorReading)
            .where(SensorReading.sensor_id == sensor.id)
            .order_by(SensorReading.recorded_at.desc())
            .limit(1)
        )
        reading = reading_result.scalar_one_or_none()
        if reading:
            readings.append({
                "sensor_id": str(sensor.id),
                "sensor_type": sensor.type.value,
                "value": reading.value_numeric,
                "timestamp": reading.recorded_at.isoformat(),
            })

    return {"device_id": str(device_id), "readings": readings}
