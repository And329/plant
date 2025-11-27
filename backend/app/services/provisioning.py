from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Actuator, Device, Sensor
from app.models.enums import ActuatorType, SensorType

SENSOR_DEFAULTS: list[tuple[SensorType, str]] = [
    (SensorType.SOIL_MOISTURE, "%"),
    (SensorType.AIR_TEMPERATURE, "C"),
    (SensorType.WATER_LEVEL, "%"),
]

ACTUATOR_DEFAULTS: list[ActuatorType] = [
    ActuatorType.PUMP,
    ActuatorType.LAMP,
]


async def ensure_default_components(
    session: AsyncSession, device: Device
) -> tuple[list[Sensor], list[Actuator]]:
    sensors: list[Sensor] = []
    actuators: list[Actuator] = []

    for sensor_type, unit in SENSOR_DEFAULTS:
        result = await session.execute(
            select(Sensor).where(Sensor.device_id == device.id, Sensor.type == sensor_type)
        )
        sensor = result.scalar_one_or_none()
        if sensor is None:
            sensor = Sensor(id=uuid4(), device_id=device.id, type=sensor_type, unit=unit)
            session.add(sensor)
        sensors.append(sensor)

    for actuator_type in ACTUATOR_DEFAULTS:
        result = await session.execute(
            select(Actuator).where(Actuator.device_id == device.id, Actuator.type == actuator_type)
        )
        actuator = result.scalar_one_or_none()
        if actuator is None:
            actuator = Actuator(id=uuid4(), device_id=device.id, type=actuator_type)
            session.add(actuator)
        actuators.append(actuator)

    return sensors, actuators
