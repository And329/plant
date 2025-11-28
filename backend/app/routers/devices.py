import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.deps import get_current_user, get_db_session
from app.models.entities import AutomationProfile, Device, Actuator, Sensor, User
from app.schemas.device import (
    ActuatorOut,
    AutomationProfileIn,
    AutomationProfileOut,
    AutomationProfilePatch,
    DeviceClaimIn,
    DeviceCreate,
    DeviceConfigOut,
    DeviceOut,
    DeviceProvisionResponse,
    SensorOut,
)
from app.services.provisioning import ensure_default_components
from app.schemas.device import AutomationProfileOut  # re-export for forward ref resolution

router = APIRouter(prefix="/devices", tags=["devices"])


def _to_device_out(device: Device) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        name=device.name,
        model=device.model,
        status=device.status,
        last_seen=device.last_seen,
        sensors=[SensorOut.model_validate(s) for s in (device.sensors or [])],
        actuators=[ActuatorOut.model_validate(a) for a in (device.actuators or [])],
        automation_profile=AutomationProfileOut.model_validate(device.automation_profile)
        if device.automation_profile
        else None,
    )


@router.get("", response_model=list[DeviceOut])
async def list_devices(user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.sensors), selectinload(Device.actuators), selectinload(Device.automation_profile))
        .where(Device.user_id == user.id)
    )
    devices = result.scalars().all()
    return [_to_device_out(device) for device in devices]


@router.post("", response_model=DeviceProvisionResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    payload: DeviceCreate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    secret = secrets.token_urlsafe(32)
    owner_id = None
    if payload.owner_email:
        result = await session.execute(select(User).where(User.email == payload.owner_email))
        owner = result.scalar_one_or_none()
        if owner is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner email not found")
        owner_id = owner.id
    elif payload.assign_to_self:
        owner_id = user.id

    device = Device(
        name=payload.name,
        model=payload.model,
        user_id=owner_id,
        secret_hash=get_password_hash(secret),
    )
    session.add(device)
    sensors, actuators = await ensure_default_components(session, device)
    await session.commit()
    await session.refresh(device)
    return DeviceProvisionResponse(
        device=DeviceOut.model_validate(device),
        secret=secret,
        sensor_ids={s.type.value: str(s.id) for s in sensors},
        actuator_ids={a.type.value: str(a.id) for a in actuators},
    )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.sensors), selectinload(Device.actuators), selectinload(Device.automation_profile))
        .where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    await session.delete(device)
    await session.commit()
    return None


@router.get("/{device_id}/config", response_model=DeviceConfigOut)
async def get_device_config(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    sensor_rows = (await session.execute(select(Sensor).where(Sensor.device_id == device.id))).scalars().all()
    actuator_rows = (await session.execute(select(Actuator).where(Actuator.device_id == device.id))).scalars().all()
    return DeviceConfigOut(
        device_id=device.id,
        device_secret=None,  # secret not retrievable after creation
        sensor_ids={s.type.value: str(s.id) for s in sensor_rows},
        actuator_ids={a.type.value: str(a.id) for a in actuator_rows},
    )


@router.post("/claim", response_model=DeviceOut)
async def claim_device(
    payload: DeviceClaimIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == payload.device_id))
    device = result.scalar_one_or_none()
    if device is None or not verify_password(payload.device_secret, device.secret_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid device credentials")
    if device.user_id and device.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device already claimed")

    device.user_id = user.id
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return DeviceOut.model_validate(device)


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: UUID, user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)
):
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.sensors), selectinload(Device.actuators), selectinload(Device.automation_profile))
        .where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return _to_device_out(device)


@router.put("/{device_id}/automation", response_model=AutomationProfileOut)
async def upsert_automation_profile(
    device_id: UUID,
    payload: AutomationProfilePatch = Body(...),
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    # Eager load current profile to avoid lazy loading outside greenlet
    profile = device.automation_profile or AutomationProfile(device_id=device.id)

    # Merge existing values with provided partial payload and defaults
    merged = {
        "soil_moisture_min": profile.soil_moisture_min if profile.soil_moisture_min is not None else 30.0,
        "soil_moisture_max": profile.soil_moisture_max if profile.soil_moisture_max is not None else 70.0,
        "temp_min": profile.temp_min if profile.temp_min is not None else 15.0,
        "temp_max": profile.temp_max if profile.temp_max is not None else 30.0,
        "min_water_level": profile.min_water_level if profile.min_water_level is not None else 20.0,
        "watering_duration_sec": profile.watering_duration_sec if profile.watering_duration_sec is not None else 20,
        "watering_cooldown_min": profile.watering_cooldown_min if profile.watering_cooldown_min is not None else 60,
        "lamp_schedule": profile.lamp_schedule if profile.lamp_schedule is not None else None,
    }
    incoming = {k: v for k, v in payload.model_dump().items() if v is not None}
    merged.update(incoming)

    # Basic sanity checks when values provided
    if merged["soil_moisture_min"] is not None and merged["soil_moisture_min"] <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="soil_moisture_min must be > 0")
    if merged["soil_moisture_max"] is not None and merged["soil_moisture_max"] <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="soil_moisture_max must be > 0")

    for field, value in merged.items():
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
