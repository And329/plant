from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.entities import Alert, AutomationProfile, Command, Device
from app.models.enums import ActuatorType, AlertSeverity, AlertType, CommandType, SensorType
from app.services.notifications import NotificationService


class AutomationWorker:
    """Processes telemetry batches and issues commands/alerts."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis: Redis | None = Redis.from_url(self.settings.redis_url, decode_responses=True)
        self.notification_service = NotificationService()
        self._stop = asyncio.Event()

    async def start(self) -> None:
        while not self._stop.is_set():
            try:
                await self._poll_once()
            except Exception:  # pragma: no cover - worker resiliency
                await asyncio.sleep(1)

    def stop(self) -> None:
        self._stop.set()

    async def _poll_once(self) -> None:
        if self.redis is None:
            await asyncio.sleep(5)
            return
        streams = await self.redis.xread({"telemetry": "$"}, block=5000, count=10)
        for _stream, entries in streams or []:
            for entry_id, payload in entries:
                await self._handle_entry(payload)
                await self.redis.xdel("telemetry", entry_id)

    async def _handle_entry(self, payload: Dict[str, str]) -> None:
        async with AsyncSessionLocal() as session:
            device_id = payload["device_id"]
            device_uuid = UUID(device_id)
            result = await session.execute(
                select(Device)
                .options(
                    selectinload(Device.sensors),
                    selectinload(Device.owner),
                    selectinload(Device.automation_profile),
                    selectinload(Device.actuators),
                )
                .where(Device.id == device_uuid)
            )
            device = result.scalar_one_or_none()
            if device is None:
                return
            items_raw = payload.get("items")
            if not items_raw:
                data: list[dict[str, Any]] = []
            else:
                data = json.loads(items_raw)
            await self._evaluate_and_apply(session, device, data)

    async def _evaluate_and_apply(self, session: AsyncSession, device: Device, readings: list[dict[str, Any]]):
        if not readings:
            return
        result = await session.execute(
            select(AutomationProfile).where(AutomationProfile.device_id == device.id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return

        latest = {}
        for reading in readings:
            latest[reading["sensor_id"]] = reading

        metric_by_type = self._map_by_sensor_type(device, latest)
        commands: list[Command] = []
        alerts: list[Alert] = []

        soil_value = metric_by_type.get(SensorType.SOIL_MOISTURE)
        pump_actuator = next((act for act in device.actuators if act.type == ActuatorType.PUMP), None)
        if soil_value is not None and soil_value < profile.soil_moisture_min:
            if await self._can_water(session, device.id, profile):
                commands.append(
                    Command(
                        device_id=device.id,
                        command=CommandType.PULSE,
                        payload={"duration": profile.watering_duration_sec},
                        actuator_id=pump_actuator.id if pump_actuator else None,
                    )
                )
            else:
                alerts.append(
                    Alert(
                        device_id=device.id,
                        type=AlertType.WATERING_COOLDOWN,
                        severity=AlertSeverity.WARN,
                        message="Watering cooldown active",
                    )
                )

        temp_value = metric_by_type.get(SensorType.AIR_TEMPERATURE)
        if temp_value is not None:
            if temp_value > profile.temp_max:
                alerts.append(
                    Alert(
                        device_id=device.id,
                        type=AlertType.TEMP_HIGH,
                        severity=AlertSeverity.WARN,
                        message="Temperature is above threshold",
                    )
                )
            elif temp_value < profile.temp_min:
                alerts.append(
                    Alert(
                        device_id=device.id,
                        type=AlertType.TEMP_LOW,
                        severity=AlertSeverity.WARN,
                        message="Temperature is below threshold",
                    )
                )

        water_level = metric_by_type.get(SensorType.WATER_LEVEL)
        if water_level is not None and water_level < profile.min_water_level:
            alerts.append(
                Alert(
                    device_id=device.id,
                    type=AlertType.WATER_LOW,
                    severity=AlertSeverity.CRITICAL,
                    message="Reservoir water level low",
                )
            )

        lamp_command = self._evaluate_light_cycle(device, profile)
        if lamp_command is not None:
            commands.append(lamp_command)

        for command in commands:
            session.add(command)
        for alert in alerts:
            session.add(alert)
            await self.notification_service.notify_alert(device.owner, alert)
        if commands or alerts:
            await session.commit()

    async def _can_water(self, session: AsyncSession, device_id, profile: AutomationProfile) -> bool:
        result = await session.execute(
            select(Command)
            .where(Command.device_id == device_id, Command.command == CommandType.PULSE)
            .order_by(Command.created_at.desc())
            .limit(1)
        )
        last_command = result.scalar_one_or_none()
        if last_command is None:
            return True
        threshold = datetime.now(timezone.utc) - timedelta(minutes=profile.watering_cooldown_min)
        return last_command.created_at < threshold

    def _map_by_sensor_type(self, device: Device, latest: dict[str, dict[str, Any]]):
        mapping: dict[SensorType, float] = {}
        for sensor in device.sensors:
            payload = latest.get(str(sensor.id))
            if payload is None:
                continue
            mapping[sensor.type] = payload["value"]
        return mapping

    def _evaluate_light_cycle(self, device: Device, profile: AutomationProfile) -> Command | None:
        schedule = profile.lamp_schedule or {}
        on_minutes = schedule.get("on_minutes")
        off_minutes = schedule.get("off_minutes")
        if not on_minutes or not off_minutes:
            return None
        lamp = next((act for act in device.actuators if act.type == ActuatorType.LAMP), None)
        if lamp is None:
            return None

        now = datetime.now(timezone.utc)
        last_change = lamp.last_command_at or lamp.created_at or now
        elapsed = now - last_change

        if lamp.state == "on":
            if elapsed >= timedelta(minutes=on_minutes):
                return Command(device_id=device.id, actuator_id=lamp.id, command=CommandType.OFF)
        else:
            if elapsed >= timedelta(minutes=off_minutes):
                return Command(device_id=device.id, actuator_id=lamp.id, command=CommandType.ON)
        return None


async def main():  # pragma: no cover - script entry
    worker = AutomationWorker()
    try:
        await worker.start()
    finally:
        if worker.redis is not None:
            await worker.redis.close()


if __name__ == "__main__":  # pragma: no cover - script entry
    asyncio.run(main())
