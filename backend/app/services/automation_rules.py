"""Modular automation rules for plant monitoring.

Each rule is a self-contained class that:
1. Checks if it should run (has required data)
2. Evaluates conditions
3. Returns commands/alerts with reasoning
4. Can be tested in isolation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.models.entities import Alert, AutomationProfile, Command, Device
from app.models.enums import (
    ActuatorType,
    AlertSeverity,
    AlertType,
    CommandType,
    SensorType,
)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    """Coerce naive datetimes to UTC-aware for safe arithmetic."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class RuleContext:
    """Context provided to automation rules."""

    device: Device
    profile: AutomationProfile
    sensor_readings: dict[SensorType, float]  # Latest reading per sensor type
    last_commands: dict[ActuatorType, Command | None]  # Last command per actuator


@dataclass
class RuleResult:
    """Result of running an automation rule."""

    rule_name: str
    executed: bool
    reason: str  # Human-readable explanation
    commands: list[Command]
    alerts: list[Alert]

    @property
    def has_actions(self) -> bool:
        return bool(self.commands or self.alerts)


class AutomationRule(ABC):
    """Base class for all automation rules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Rule name for logging and debugging."""
        pass

    @abstractmethod
    def can_run(self, ctx: RuleContext) -> bool:
        """Check if rule has all required data to run."""
        pass

    @abstractmethod
    def evaluate(self, ctx: RuleContext) -> RuleResult:
        """Evaluate rule and return actions to take."""
        pass


class SoilMoistureRule(AutomationRule):
    """Monitors soil moisture and triggers watering when too dry."""

    @property
    def name(self) -> str:
        return "soil_moisture_control"

    def can_run(self, ctx: RuleContext) -> bool:
        return (
            SensorType.SOIL_MOISTURE in ctx.sensor_readings
            and ctx.profile.soil_moisture_min is not None
            and any(a.type == ActuatorType.PUMP for a in ctx.device.actuators)
        )

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        moisture = ctx.sensor_readings[SensorType.SOIL_MOISTURE]
        min_threshold = ctx.profile.soil_moisture_min

        if moisture >= min_threshold:
            return RuleResult(
                rule_name=self.name,
                executed=True,
                reason=f"Soil moisture {moisture}% is above minimum {min_threshold}%",
                commands=[],
                alerts=[],
            )

        # Moisture too low - check cooldown
        pump = next(
            (a for a in ctx.device.actuators if a.type == ActuatorType.PUMP), None
        )
        last_pump_cmd = ctx.last_commands.get(ActuatorType.PUMP)

        if last_pump_cmd:
            cooldown_minutes = ctx.profile.watering_cooldown_min
            last_created = _ensure_aware(last_pump_cmd.created_at) or datetime.now(
                timezone.utc
            )
            elapsed = datetime.now(timezone.utc) - last_created
            if elapsed < timedelta(minutes=cooldown_minutes):
                return RuleResult(
                    rule_name=self.name,
                    executed=True,
                    reason=f"Soil moisture low ({moisture}%), but watering on cooldown ({elapsed.seconds // 60}/{cooldown_minutes} min)",
                    commands=[],
                    alerts=[
                        Alert(
                            device_id=ctx.device.id,
                            type=AlertType.WATERING_COOLDOWN,
                            severity=AlertSeverity.WARN,
                            message="Watering cooldown active",
                        )
                    ],
                )

        # Can water
        return RuleResult(
            rule_name=self.name,
            executed=True,
            reason=f"Soil moisture {moisture}% below minimum {min_threshold}%, triggering watering",
            commands=[
                Command(
                    device_id=ctx.device.id,
                    actuator_id=pump.id if pump else None,
                    command=CommandType.PULSE,
                    payload={"duration": ctx.profile.watering_duration_sec},
                )
            ],
            alerts=[],
        )


class TemperatureAlertRule(AutomationRule):
    """Monitors temperature and creates alerts for out-of-range values."""

    @property
    def name(self) -> str:
        return "temperature_alerts"

    def can_run(self, ctx: RuleContext) -> bool:
        return (
            SensorType.AIR_TEMPERATURE in ctx.sensor_readings
            and ctx.profile.temp_min is not None
            and ctx.profile.temp_max is not None
        )

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        temp = ctx.sensor_readings[SensorType.AIR_TEMPERATURE]
        temp_min = ctx.profile.temp_min
        temp_max = ctx.profile.temp_max

        if temp < temp_min:
            return RuleResult(
                rule_name=self.name,
                executed=True,
                reason=f"Temperature {temp}°C is below minimum {temp_min}°C",
                commands=[],
                alerts=[
                    Alert(
                        device_id=ctx.device.id,
                        type=AlertType.TEMP_LOW,
                        severity=AlertSeverity.WARN,
                        message=f"Temperature is below threshold ({temp}°C < {temp_min}°C)",
                    )
                ],
            )

        if temp > temp_max:
            return RuleResult(
                rule_name=self.name,
                executed=True,
                reason=f"Temperature {temp}°C is above maximum {temp_max}°C",
                commands=[],
                alerts=[
                    Alert(
                        device_id=ctx.device.id,
                        type=AlertType.TEMP_HIGH,
                        severity=AlertSeverity.WARN,
                        message=f"Temperature is above threshold ({temp}°C > {temp_max}°C)",
                    )
                ],
            )

        return RuleResult(
            rule_name=self.name,
            executed=True,
            reason=f"Temperature {temp}°C is within range ({temp_min}°C - {temp_max}°C)",
            commands=[],
            alerts=[],
        )


class WaterLevelAlertRule(AutomationRule):
    """Monitors water reservoir level and alerts when low."""

    @property
    def name(self) -> str:
        return "water_level_monitor"

    def can_run(self, ctx: RuleContext) -> bool:
        return SensorType.WATER_LEVEL in ctx.sensor_readings

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        level = ctx.sensor_readings[SensorType.WATER_LEVEL]
        min_level = ctx.profile.min_water_level

        if level < min_level:
            return RuleResult(
                rule_name=self.name,
                executed=True,
                reason=f"Water level {level}% below minimum {min_level}%",
                commands=[],
                alerts=[
                    Alert(
                        device_id=ctx.device.id,
                        type=AlertType.WATER_LOW,
                        severity=AlertSeverity.CRITICAL,
                        message=f"Reservoir water level low ({level}%)",
                    )
                ],
            )

        return RuleResult(
            rule_name=self.name,
            executed=True,
            reason=f"Water level {level}% is adequate (>{min_level}%)",
            commands=[],
            alerts=[],
        )


class LightCycleRule(AutomationRule):
    """Controls lamp on/off cycles based on schedule."""

    @property
    def name(self) -> str:
        return "light_cycle_control"

    def can_run(self, ctx: RuleContext) -> bool:
        schedule = ctx.profile.lamp_schedule or {}
        return (
            schedule.get("on_minutes") is not None
            and schedule.get("off_minutes") is not None
            and any(a.type == ActuatorType.LAMP for a in ctx.device.actuators)
        )

    def evaluate(self, ctx: RuleContext) -> RuleResult:
        schedule = ctx.profile.lamp_schedule
        on_minutes = schedule["on_minutes"]
        off_minutes = schedule["off_minutes"]

        lamp = next(
            (a for a in ctx.device.actuators if a.type == ActuatorType.LAMP), None
        )
        if not lamp:
            return RuleResult(
                rule_name=self.name,
                executed=False,
                reason="No lamp actuator found",
                commands=[],
                alerts=[],
            )

        now = datetime.now(timezone.utc)
        last_change = (
            _ensure_aware(lamp.last_command_at)
            or _ensure_aware(lamp.created_at)
            or now
        )
        elapsed = now - last_change
        elapsed_minutes = int(elapsed.total_seconds() / 60)

        if lamp.state == "on":
            if elapsed >= timedelta(minutes=on_minutes):
                return RuleResult(
                    rule_name=self.name,
                    executed=True,
                    reason=f"Lamp on for {elapsed_minutes}/{on_minutes} minutes, turning off",
                    commands=[
                        Command(
                            device_id=ctx.device.id,
                            actuator_id=lamp.id,
                            command=CommandType.OFF,
                        )
                    ],
                    alerts=[],
                )
            return RuleResult(
                rule_name=self.name,
                executed=True,
                reason=f"Lamp on for {elapsed_minutes}/{on_minutes} minutes, continuing",
                commands=[],
                alerts=[],
            )
        else:
            if elapsed >= timedelta(minutes=off_minutes):
                return RuleResult(
                    rule_name=self.name,
                    executed=True,
                    reason=f"Lamp off for {elapsed_minutes}/{off_minutes} minutes, turning on",
                    commands=[
                        Command(
                            device_id=ctx.device.id,
                            actuator_id=lamp.id,
                            command=CommandType.ON,
                        )
                    ],
                    alerts=[],
                )
            return RuleResult(
                rule_name=self.name,
                executed=True,
                reason=f"Lamp off for {elapsed_minutes}/{off_minutes} minutes, continuing",
                commands=[],
                alerts=[],
            )


# Registry of all available rules
ALL_RULES: list[AutomationRule] = [
    SoilMoistureRule(),
    TemperatureAlertRule(),
    WaterLevelAlertRule(),
    LightCycleRule(),
]
