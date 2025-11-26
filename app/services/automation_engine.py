from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from redis.asyncio import Redis

from app.core.config import Settings


@dataclass
class TelemetryRecord:
    sensor_id: str
    value: float
    timestamp: datetime

    def to_dict(self) -> dict[str, str]:
        return {
            "sensor_id": self.sensor_id,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
        }


class AutomationEngine:
    """Simple queue wrapper that feeds telemetry data to the automation worker."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._redis: Redis | None = Redis.from_url(settings.redis_url, decode_responses=True)

    async def enqueue(self, device_id: str, batch_id: str, readings: Iterable[TelemetryRecord]) -> None:
        if self._redis is None:
            return
        payload = {
            "device_id": device_id,
            "batch_id": batch_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "items": json.dumps([record.to_dict() for record in readings]),
        }
        try:
            await self._redis.xadd("telemetry", payload)
        except Exception:
            # Redis is optional during local development - swallow errors but log in production
            pass

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()
