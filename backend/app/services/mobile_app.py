"""Helpers for managing the mobile app APK metadata and storage."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.app_settings import get_setting, set_setting

APK_SETTING_KEY = "mobile_apk_metadata"
APK_DIR = Path("data/mobile_apk")


def _human_size(size_bytes: int | None) -> str | None:
    if size_bytes is None:
        return None
    step = 1024.0
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if size < step:
            return f"{size:.1f} {unit}"
        size /= step
    return f"{size:.1f} TB"


async def save_apk_metadata(session: AsyncSession, *, path: Path, original_name: str) -> dict[str, Any]:
    """Persist metadata for the latest APK."""
    APK_DIR.mkdir(parents=True, exist_ok=True)
    metadata = {
        "path": str(path.resolve()),
        "original_name": original_name,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await set_setting(session, APK_SETTING_KEY, json.dumps(metadata))
    return metadata


async def get_apk_metadata(session: AsyncSession) -> dict[str, Any] | None:
    """Load APK metadata with derived fields (size, existence)."""
    raw = await get_setting(session, APK_SETTING_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None

    path = Path(data.get("path", ""))
    exists = path.is_file()
    size_bytes = path.stat().st_size if exists else None
    return {
        "path": str(path),
        "original_name": data.get("original_name"),
        "uploaded_at": data.get("uploaded_at"),
        "size_bytes": size_bytes,
        "size_human": _human_size(size_bytes),
        "exists": exists,
    }
