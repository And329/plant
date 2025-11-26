from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, Float, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import GUID
from app.models.enums import (
    ActuatorType,
    AlertSeverity,
    AlertType,
    CommandStatus,
    CommandType,
    DeviceStatus,
    SensorType,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    locale: Mapped[str | None]
    alert_preferences: Mapped[dict | None] = mapped_column(JSON)

    devices: Mapped[List["Device"]] = relationship(back_populates="owner")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str]
    model: Mapped[str | None]
    status: Mapped[DeviceStatus] = mapped_column(Enum(DeviceStatus), default=DeviceStatus.PROVISIONED)
    secret_hash: Mapped[str]
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User | None] = relationship(back_populates="devices")
    sensors: Mapped[List["Sensor"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    actuators: Mapped[List["Actuator"]] = relationship(back_populates="device", cascade="all, delete-orphan")
    automation_profile: Mapped[Optional["AutomationProfile"]] = relationship(
        back_populates="device", cascade="all, delete-orphan", uselist=False
    )
    commands: Mapped[List["Command"]] = relationship(back_populates="device")


class Sensor(TimestampMixin, Base):
    __tablename__ = "sensors"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    type: Mapped[SensorType] = mapped_column(Enum(SensorType), nullable=False)
    unit: Mapped[str]
    calibration: Mapped[dict | None] = mapped_column(JSON)

    device: Mapped[Device] = relationship(back_populates="sensors")
    readings: Mapped[List["SensorReading"]] = relationship(
        back_populates="sensor", cascade="all, delete-orphan"
    )


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    sensor_id: Mapped[UUID] = mapped_column(ForeignKey("sensors.id", ondelete="CASCADE"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_numeric: Mapped[float] = mapped_column(Float)
    raw: Mapped[dict | None] = mapped_column(JSON)

    sensor: Mapped[Sensor] = relationship(back_populates="readings")


class Actuator(TimestampMixin, Base):
    __tablename__ = "actuators"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    type: Mapped[ActuatorType] = mapped_column(Enum(ActuatorType))
    state: Mapped[str] = mapped_column(default="off")
    last_command_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    device: Mapped[Device] = relationship(back_populates="actuators")
    commands: Mapped[List["Command"]] = relationship(back_populates="actuator")


class AutomationProfile(TimestampMixin, Base):
    __tablename__ = "automation_profiles"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), unique=True)
    soil_moisture_min: Mapped[float]
    soil_moisture_max: Mapped[float]
    temp_min: Mapped[float]
    temp_max: Mapped[float]
    min_water_level: Mapped[float] = mapped_column(default=20)
    watering_duration_sec: Mapped[int] = mapped_column(default=20)
    watering_cooldown_min: Mapped[int] = mapped_column(default=60)
    lamp_schedule: Mapped[dict | None] = mapped_column(JSON)

    device: Mapped[Device] = relationship(back_populates="automation_profile")


class Command(TimestampMixin, Base):
    __tablename__ = "commands"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    actuator_id: Mapped[UUID | None] = mapped_column(GUID(), ForeignKey("actuators.id"), nullable=True)
    command: Mapped[CommandType] = mapped_column(Enum(CommandType))
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[CommandStatus] = mapped_column(Enum(CommandStatus), default=CommandStatus.PENDING)
    message: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    device: Mapped[Device] = relationship(back_populates="commands")
    actuator: Mapped[Actuator | None] = relationship(back_populates="commands")


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    type: Mapped[AlertType] = mapped_column(Enum(AlertType))
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity))
    message: Mapped[str] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    device: Mapped[Device] = relationship()
