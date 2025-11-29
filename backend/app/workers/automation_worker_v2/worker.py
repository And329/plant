"""Refactored automation worker using modular rule system with debug logging."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.entities import (
    AutomationExecutionLog,
    AutomationProfile,
    Command,
    Device,
)
from app.models.enums import ActuatorType, CommandType, SensorType
from app.services.automation_rules import (
    ALL_RULES,
    RuleContext,
    RuleResult,
)
from app.services.notifications import NotificationService

log = logging.getLogger("automation-worker")


class AutomationWorkerV2:
    """Processes telemetry batches using modular automation rules."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis: Redis | None = Redis.from_url(
            self.settings.redis_url, decode_responses=True
        )
        self.notification_service = NotificationService()
        self._stop = asyncio.Event()

    async def start(self) -> None:
        log.info("Automation worker V2 starting with %d rules", len(ALL_RULES))
        while not self._stop.is_set():
            try:
                await self._poll_once()
            except Exception as exc:
                log.exception("Worker error: %s", exc)
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
            batch_id = payload.get("batch_id", "unknown")
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
                log.warning("Device %s not found", device_id)
                return

            items_raw = payload.get("items")
            if not items_raw:
                data: list[dict[str, Any]] = []
            else:
                data = json.loads(items_raw)

            await self._evaluate_and_apply(session, device, batch_id, data)

    async def _evaluate_and_apply(
        self,
        session: AsyncSession,
        device: Device,
        batch_id: str,
        readings: list[dict[str, Any]],
    ):
        if not readings:
            return

        # Get automation profile
        profile = device.automation_profile
        if profile is None:
            log.debug("Device %s has no automation profile", device.id)
            return

        # Build sensor readings map
        latest = {}
        for reading in readings:
            latest[reading["sensor_id"]] = reading

        sensor_readings = self._map_by_sensor_type(device, latest)

        # Get last commands per actuator for cooldown checks
        last_commands = await self._get_last_commands(session, device)

        # Build rule context
        ctx = RuleContext(
            device=device,
            profile=profile,
            sensor_readings=sensor_readings,
            last_commands=last_commands,
        )

        # Run all rules
        results: list[RuleResult] = []
        all_commands: list[Command] = []
        all_alerts: list = []

        for rule in ALL_RULES:
            if not rule.can_run(ctx):
                log.debug("Rule %s skipped (missing data)", rule.name)
                results.append(
                    RuleResult(
                        rule_name=rule.name,
                        executed=False,
                        reason="Missing required data",
                        commands=[],
                        alerts=[],
                    )
                )
                continue

            result = rule.evaluate(ctx)
            results.append(result)
            all_commands.extend(result.commands)
            all_alerts.extend(result.alerts)

            if result.has_actions:
                log.info(
                    "Rule %s: %s -> %d commands, %d alerts",
                    result.rule_name,
                    result.reason,
                    len(result.commands),
                    len(result.alerts),
                )
            else:
                log.debug("Rule %s: %s", result.rule_name, result.reason)

        # Save commands and alerts
        for command in all_commands:
            session.add(command)
        for alert in all_alerts:
            session.add(alert)
            if device.owner is not None:
                await self.notification_service.notify_alert(device.owner, alert)

        # Log execution for debugging (optional - table may not exist yet)
        try:
            exec_log = AutomationExecutionLog(
                device_id=device.id,
                telemetry_batch_id=batch_id,
                rules_executed={
                    r.rule_name: {
                        "executed": r.executed,
                        "reason": r.reason,
                        "commands": len(r.commands),
                        "alerts": len(r.alerts),
                    }
                    for r in results
                },
                commands_issued=len(all_commands),
                alerts_created=len(all_alerts),
                sensor_readings={k.value: v for k, v in sensor_readings.items()},
                profile_snapshot={
                    "soil_moisture_min": profile.soil_moisture_min,
                    "soil_moisture_max": profile.soil_moisture_max,
                    "temp_min": profile.temp_min,
                    "temp_max": profile.temp_max,
                    "min_water_level": profile.min_water_level,
                    "watering_duration_sec": profile.watering_duration_sec,
                    "watering_cooldown_min": profile.watering_cooldown_min,
                    "lamp_schedule": profile.lamp_schedule,
                },
            )
            session.add(exec_log)
        except Exception as e:
            log.debug("Could not save execution log (table may not exist): %s", e)

        if all_commands or all_alerts:
            await session.commit()
            log.info(
                "Device %s automation: %d commands, %d alerts (batch %s)",
                device.id,
                len(all_commands),
                len(all_alerts),
                batch_id,
            )

    async def _get_last_commands(
        self, session: AsyncSession, device: Device
    ) -> dict[ActuatorType, Command | None]:
        """Get most recent command per actuator type for cooldown checks."""
        result = {}
        for actuator in device.actuators:
            cmd_result = await session.execute(
                select(Command)
                .where(
                    Command.device_id == device.id, Command.actuator_id == actuator.id
                )
                .order_by(Command.created_at.desc())
                .limit(1)
            )
            result[actuator.type] = cmd_result.scalar_one_or_none()
        return result

    def _map_by_sensor_type(self, device: Device, latest: dict[str, dict[str, Any]]):
        mapping: dict[SensorType, float] = {}
        for sensor in device.sensors:
            payload = latest.get(str(sensor.id))
            if payload is None:
                continue
            mapping[sensor.type] = payload["value"]
        return mapping
