from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
from app.models.entities import Actuator, AutomationProfile, Device, Sensor, User
from app.models.enums import ActuatorType, SensorType

DEMO_ACTUATOR_IDS = {
    ActuatorType.PUMP: UUID("21111111-1111-1111-1111-111111111111"),
    ActuatorType.LAMP: UUID("31111111-1111-1111-1111-111111111111"),
}
DEMO_SENSOR_IDS = {
    SensorType.SOIL_MOISTURE: UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    SensorType.AIR_TEMPERATURE: UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    SensorType.WATER_LEVEL: UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
}


async def bootstrap(seed_demo: bool, email: str, password: str) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if not seed_demo:
        print("Database ready. No demo fixtures created.")
        return

    device_id = UUID("11111111-1111-1111-1111-111111111111")
    secret = "demo-device-secret"

    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            user = User(email=email, password_hash=get_password_hash(password), locale="en")
            session.add(user)
            await session.flush()

        device = await session.get(Device, device_id)
        if device is None:
            device = Device(
                id=device_id,
                name="Demo planter",
                model="Raspberry Pi",
                user_id=user.id,
                secret_hash=get_password_hash(secret),
            )
            session.add(device)
            await session.flush()
        else:
            device.user_id = user.id
            session.add(device)

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
                )
            )

        await session.commit()

    print("Demo data ready!")
    print(f"User email: {email}")
    print(f"User password: {password}")
    print(f"Device ID: {device_id}")
    print(f"Device secret: {secret}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize database and optional demo fixtures.")
    parser.add_argument("--seed-demo", action="store_true", help="Seed demo user/device for quick testing")
    parser.add_argument("--demo-email", default="demo@plant.local", help="Demo user email")
    parser.add_argument("--demo-password", default="demo1234", help="Demo user password")
    args = parser.parse_args()
    asyncio.run(bootstrap(args.seed_demo, args.demo_email, args.demo_password))


if __name__ == "__main__":
    main()
