from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import AppSetting


async def get_setting(session: AsyncSession, key: str) -> Optional[str]:
    setting = await session.get(AppSetting, key)
    return setting.value if setting else None


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    setting = await session.get(AppSetting, key)
    if setting:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        session.add(setting)
    await session.commit()


async def delete_setting(session: AsyncSession, key: str) -> None:
    setting = await session.get(AppSetting, key)
    if setting:
        await session.delete(setting)
        await session.commit()
