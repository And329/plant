from __future__ import annotations

import argparse
import asyncio
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.entities import Device, User


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
        await session.commit()
        print("Device provisioned!")
        print(f"  Name: {device.name}")
        print(f"  ID: {device_id}")
        print(f"  Secret: {secret}")
        if owner_email:
            print(f"  Assigned to: {owner_email}")
        else:
            print("  Assigned to: <unclaimed>")


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
