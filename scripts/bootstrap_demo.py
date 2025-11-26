from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.entities import Actuator, AutomationProfile, Device, Sensor, User
from app.models.enums import ActuatorType, SensorType

DEMO_USER_EMAIL = "demo@plant.local"
DEMO_USER_PASSWORD = "demo1234"
DEMO_DEVICE_ID = UUID("11111111-1111-1111-1111-111111111111")
DEMO_DEVICE_SECRET = "demo-device-secret"
DEMO_ACTUATOR_IDS = {
    ActuatorType.PUMP: UUID("21111111-1111-1111-1111-111111111111"),
    ActuatorType.LAMP: UUID("31111111-1111-1111-1111-111111111111"),
}
DEMO_SENSOR_IDS = {
    SensorType.SOIL_MOISTURE: UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    SensorType.AIR_TEMPERATURE: UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    SensorType.WATER_LEVEL: UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
}


async def bootstrap_demo() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.email == DEMO_USER_EMAIL))
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=DEMO_USER_EMAIL,
                password_hash=get_password_hash(DEMO_USER_PASSWORD),
                locale="en",
            )
            session.add(user)
            await session.flush()

        device = await session.get(Device, DEMO_DEVICE_ID)
        if device is None:
            device = Device(
                id=DEMO_DEVICE_ID,
                name="Demo planter",
                model="Raspberry Pi",
                user_id=user.id,
                secret_hash=get_password_hash(DEMO_DEVICE_SECRET),
            )
            session.add(device)
            await session.flush()

        for sensor_type, sensor_id in DEMO_SENSOR_IDS.items():
            sensor = await session.get(Sensor, sensor_id)
            if sensor is None:
                session.add(
                    Sensor(
                        id=sensor_id,
                        device_id=device.id,
                        type=sensor_type,
                        unit="%" if sensor_type != SensorType.AIR_TEMPERATURE else "C",
                    )
                )

        for actuator_type, actuator_id in DEMO_ACTUATOR_IDS.items():
            actuator = await session.get(Actuator, actuator_id)
            if actuator is None:
                session.add(
                    Actuator(
                        id=actuator_id,
                        device_id=device.id,
                        type=actuator_type,
                    )
                )

        profile = (
            await session.execute(select(AutomationProfile).where(AutomationProfile.device_id == device.id))
        ).scalar_one_or_none()
        if profile is None:
            session.add(
                AutomationProfile(
                    device_id=device.id,
                    soil_moisture_min=35,
                    soil_moisture_max=65,
                    temp_min=18,
                    temp_max=30,
                    min_water_level=25,
                    watering_duration_sec=10,
                    watering_cooldown_min=30,
                    lamp_schedule={"on_minutes": 30, "off_minutes": 30},
                )
            )

        await session.commit()

    print("Demo environment ready!")
    print(f"User email: {DEMO_USER_EMAIL}")
    print(f"User password: {DEMO_USER_PASSWORD}")
    print(f"Device ID: {DEMO_DEVICE_ID}")
    print(f"Device secret: {DEMO_DEVICE_SECRET}")
    print("Sensor IDs:")
    for sensor_type, sensor_id in DEMO_SENSOR_IDS.items():
        print(f"  {sensor_type.value}: {sensor_id}")


if __name__ == "__main__":
    asyncio.run(bootstrap_demo())
