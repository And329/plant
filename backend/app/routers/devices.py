import secrets
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash
from app.deps import get_app_settings, get_current_user, get_db_session
from app.models.entities import Actuator, AutomationProfile, Device, Sensor, User
from app.schemas.device import (
    ActuatorOut,
    AutomationProfileIn,
    AutomationProfileOut,
    AutomationProfilePatch,
    DeviceClaimIn,
    DeviceConfigOut,
    DeviceCreate,
    DeviceOut,
    DeviceProvisionResponse,
    SensorOut,
)  # re-export for forward ref resolution
from app.services.provisioning import ensure_default_components

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
        automation_profile=AutomationProfileOut.model_validate(
            device.automation_profile
        )
        if device.automation_profile
        else None,
    )


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    include_unclaimed: bool = False,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings=Depends(get_app_settings),
):
    # Check if user is admin
    is_admin = user.email in settings.admin_emails

    # Build query based on permissions
    if include_unclaimed and is_admin:
        # Admin requesting unclaimed devices only
        where_clause = Device.user_id == None
    elif is_admin:
        # Admin requesting their own devices (default)
        where_clause = Device.user_id == user.id
    else:
        # Regular users only see their own devices
        where_clause = Device.user_id == user.id

    result = await session.execute(
        select(Device)
        .options(
            selectinload(Device.sensors),
            selectinload(Device.actuators),
            selectinload(Device.automation_profile),
        )
        .where(where_clause)
    )
    devices = result.scalars().all()
    return [_to_device_out(device) for device in devices]


@router.post(
    "", response_model=DeviceProvisionResponse, status_code=status.HTTP_201_CREATED
)
async def register_device(
    payload: DeviceCreate,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    secret = secrets.token_urlsafe(32)
    owner_id = None
    if payload.owner_email:
        result = await session.execute(
            select(User).where(User.email == payload.owner_email)
        )
        owner = result.scalar_one_or_none()
        if owner is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Owner email not found"
            )
        owner_id = owner.id
    elif payload.assign_to_self:
        owner_id = user.id

    device = Device(
        name=payload.name,
        model=payload.model,
        user_id=owner_id,
        secret=secret,
    )
    session.add(device)
    sensors, actuators = await ensure_default_components(session, device)
    await session.commit()

    # Re-fetch device with relationships eagerly loaded
    result = await session.execute(
        select(Device)
        .options(
            selectinload(Device.sensors),
            selectinload(Device.actuators),
            selectinload(Device.automation_profile),
        )
        .where(Device.id == device.id)
    )
    device = result.scalar_one()

    return DeviceProvisionResponse(
        device=_to_device_out(device),
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
        .options(
            selectinload(Device.sensors),
            selectinload(Device.actuators),
            selectinload(Device.automation_profile),
        )
        .where(
            (Device.id == device_id)
            & ((Device.user_id == user.id) | (Device.user_id == None))
        )
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    await session.delete(device)
    await session.commit()
    return None


@router.get("/{device_id}/config", response_model=DeviceConfigOut)
async def get_device_config(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings=Depends(get_app_settings),
):
    result = await session.execute(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )

    sensor_rows = (
        (await session.execute(select(Sensor).where(Sensor.device_id == device.id)))
        .scalars()
        .all()
    )
    actuator_rows = (
        (await session.execute(select(Actuator).where(Actuator.device_id == device.id)))
        .scalars()
        .all()
    )

    # Only include secret for admins and if device is unclaimed
    is_admin = user.email in settings.admin_emails
    include_secret = is_admin and device.user_id is None

    return DeviceConfigOut(
        device_id=device.id,
        device_secret=device.secret if include_secret else None,
        sensor_ids={s.type.value: str(s.id) for s in sensor_rows},
        actuator_ids={a.type.value: str(a.id) for a in actuator_rows},
    )


@router.get("/{device_id}/secret")
async def get_device_secret(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    settings=Depends(get_app_settings),
):
    """Retrieve device secret. Only available to admins for unclaimed devices."""
    is_admin = user.email in settings.admin_emails
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can retrieve device secrets",
        )

    result = await session.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )

    if device.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot retrieve secret for claimed device",
        )

    return {"device_id": str(device.id), "secret": device.secret}


@router.post("/claim", response_model=DeviceOut)
async def claim_device(
    payload: DeviceClaimIn,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(select(Device).where(Device.id == payload.device_id))
    device = result.scalar_one_or_none()
    if device is None or device.secret != payload.device_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid device credentials"
        )
    if device.user_id and device.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Device already claimed"
        )

    device.user_id = user.id
    session.add(device)
    await session.commit()

    # Re-fetch with relationships eagerly loaded
    result = await session.execute(
        select(Device)
        .options(
            selectinload(Device.sensors),
            selectinload(Device.actuators),
            selectinload(Device.automation_profile),
        )
        .where(Device.id == device.id)
    )
    device = result.scalar_one()
    return _to_device_out(device)


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(
    device_id: UUID,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Device)
        .options(
            selectinload(Device.sensors),
            selectinload(Device.actuators),
            selectinload(Device.automation_profile),
        )
        .where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    return _to_device_out(device)


@router.put("/{device_id}/automation", response_model=AutomationProfileOut)
async def upsert_automation_profile(
    device_id: UUID,
    payload: AutomationProfilePatch = Body(...),
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.automation_profile))
        .where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )

    # Eager load current profile to avoid lazy loading outside greenlet
    profile = device.automation_profile or AutomationProfile(device_id=device.id)

    # Merge existing values with provided partial payload and defaults
    merged = {
        "soil_moisture_min": profile.soil_moisture_min
        if profile.soil_moisture_min is not None
        else 30.0,
        "soil_moisture_max": profile.soil_moisture_max
        if profile.soil_moisture_max is not None
        else 70.0,
        "temp_min": profile.temp_min if profile.temp_min is not None else 15.0,
        "temp_max": profile.temp_max if profile.temp_max is not None else 30.0,
        "min_water_level": profile.min_water_level
        if profile.min_water_level is not None
        else 20.0,
        "watering_duration_sec": profile.watering_duration_sec
        if profile.watering_duration_sec is not None
        else 20,
        "watering_cooldown_min": profile.watering_cooldown_min
        if profile.watering_cooldown_min is not None
        else 60,
        "lamp_schedule": profile.lamp_schedule
        if profile.lamp_schedule is not None
        else None,
    }
    incoming = {k: v for k, v in payload.model_dump().items() if v is not None}
    merged.update(incoming)

    # Basic sanity checks when values provided
    if merged["soil_moisture_min"] is not None and merged["soil_moisture_min"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="soil_moisture_min must be > 0",
        )
    if merged["soil_moisture_max"] is not None and merged["soil_moisture_max"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="soil_moisture_max must be > 0",
        )

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
    result = await session.execute(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    device = result.scalar_one_or_none()
    if device is None or device.automation_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation profile not configured",
        )
    return AutomationProfileOut.model_validate(device.automation_profile)
