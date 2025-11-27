from __future__ import annotations

import argparse
import asyncio
import json
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.entities import Device, User
from app.services.provisioning import ensure_default_components


async def _provision(name: str, model: str | None, owner_email: str | None) -> None:
    async with AsyncSessionLocal() as session:
        user_id: UUID | None = None
        if owner_email:
            result = await session.execute(select(User).where(User.email == owner_email))
            user = result.scalar_one_or_none()
            if user is None:
                raise SystemExit(f"User with email {owner_email} not found")
            user_id = user.id

        device_id = uuid4()
        secret = secrets.token_urlsafe(16)
        device = Device(
            id=device_id,
            name=name,
            model=model,
            user_id=user_id,
            secret_hash=get_password_hash(secret),
        )
        session.add(device)
        sensors, actuators = await ensure_default_components(session, device)
        await session.commit()
        print("Device provisioned!")
        print(f"  Name: {device.name}")
        print(f"  ID: {device_id}")
        print(f"  Secret: {secret}")
        if owner_email:
            print(f"  Assigned to: {owner_email}")
        else:
            print("  Assigned to: <unclaimed>")
        sensor_key_overrides = {"air_temperature": "temperature"}
        config = {
            "api_base_url": "http://localhost:8000",
            "device_id": str(device_id),
            "device_secret": secret,
            "sensor_ids": {
                sensor_key_overrides.get(sensor.type.value, sensor.type.value): str(sensor.id) for sensor in sensors
            },
            "actuator_ids": {actuator.type.value: str(actuator.id) for actuator in actuators},
        }
        print("  Config snippet (update api_base_url and sensor IDs as needed):")
        print(json.dumps(config, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a new plant device")
    parser.add_argument("--name", required=True, help="Friendly device name, e.g. 'Planter 42'")
    parser.add_argument("--model", default=None, help="Optional hardware model")
    parser.add_argument(
        "--owner-email",
        default=None,
        help="Assign device to existing user email (optional). Leave blank to ship unclaimed.",
    )
    args = parser.parse_args()
    asyncio.run(_provision(args.name, args.model, args.owner_email))


if __name__ == "__main__":
    main()
