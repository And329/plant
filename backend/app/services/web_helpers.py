from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from app.core.config import Settings
from app.models.entities import Device, User


def time_since(moment: datetime | None) -> tuple[str, int | None]:
    if moment is None:
        return ("never", None)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - moment
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        label = f"{seconds}s ago"
    elif seconds < 3600:
        label = f"{seconds // 60}m ago"
    elif seconds < 86400:
        label = f"{seconds // 3600}h ago"
    else:
        label = f"{seconds // 86400}d ago"
    return label, seconds


def device_connection_meta(device: Device, offline_seconds: int) -> dict[str, Any]:
    last_seen_label, seconds = time_since(device.last_seen)
    connected = seconds is not None and seconds <= offline_seconds
    iso_value = None
    if device.last_seen:
        moment = device.last_seen
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        iso_value = moment.isoformat()
    return {
        "status": "connected" if connected else "disconnected",
        "last_seen": last_seen_label,
        "connected": connected,
        "last_seen_iso": iso_value,
    }


def user_is_admin(user: User | None, settings: Settings) -> bool:
    return bool(user and user.email in (settings.admin_emails or []))


def set_session_user(request: Request, user: User, settings: Settings) -> None:
    request.session["user_id"] = str(user.id)
    request.session["user_email"] = user.email
    request.session["is_admin"] = user_is_admin(user, settings)
