import secrets

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.deps import get_current_user, get_db_session
from app.models.entities import AutomationProfile, Device
from app.schemas.device import (
    AutomationProfileIn,
    AutomationProfileOut,
    DeviceCreate,
    DeviceOut,
    DeviceProvisionResponse,
)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
async def list_devices(user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(select(Device).where(Device.user_id == user.id))
    devices = result.scalars().all()
    return [DeviceOut.model_validate(device) for device in devices]


@router.post("", response_model=DeviceProvisionResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceCreate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    secret = secrets.token_urlsafe(32)
    device = Device(
        name=payload.name,
        model=payload.model,
        user_id=user.id,
        secret_hash=get_password_hash(secret),
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return DeviceProvisionResponse(device=DeviceOut.model_validate(device), secret=secret)


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: UUID, user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)
):
    result = await session.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return DeviceOut.model_validate(device)


@router.put("/{device_id}/automation", response_model=AutomationProfileOut)
async def upsert_automation_profile(
    device_id: UUID,
    payload: AutomationProfileIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    profile = device.automation_profile or AutomationProfile(device_id=device.id)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return AutomationProfileOut.model_validate(profile)


@router.get("/{device_id}/automation", response_model=AutomationProfileOut)
async def fetch_automation_profile(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalar_one_or_none()
    if device is None or device.automation_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation profile not configured")

    return AutomationProfileOut.model_validate(device.automation_profile)
