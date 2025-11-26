from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models.entities import Alert, User


@dataclass
class NotificationChannel:
    type: str
    target: str


class NotificationService:
    """Placeholder notification service (e-mail, Telegram, etc.)."""

    async def notify_alert(self, user: User, alert: Alert) -> None:  # pragma: no cover - stub
        # In production, integrate with e-mail, push notifications, or chat bots.
        channels: Iterable[NotificationChannel] = self._resolve_channels(user)
        for _channel in channels:
            pass

    def _resolve_channels(self, user: User) -> list[NotificationChannel]:
        prefs = user.alert_preferences or {}
        channels: list[NotificationChannel] = []
        if email := prefs.get("email", user.email):
            channels.append(NotificationChannel(type="email", target=email))
        if telegram := prefs.get("telegram"):
            channels.append(NotificationChannel(type="telegram", target=telegram))
        return channels
