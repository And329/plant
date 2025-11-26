from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_automation_engine, get_current_device, get_db_session
from app.models.entities import Sensor, SensorReading
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
