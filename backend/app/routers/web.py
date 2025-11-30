from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import get_password_hash, verify_password
from app.deps import get_app_settings, get_db_session
from app.models.entities import Alert, Actuator, AutomationProfile, Command, Device, Sensor, SensorReading, User
from app.models.enums import CommandType
from app.services.app_settings import delete_setting, get_setting, set_setting
from app.services.mobile_app import APK_DIR, get_apk_metadata, save_apk_metadata
from app.services.web_helpers import device_connection_meta, set_session_user, time_since, user_is_admin
from app.services.provisioning import ensure_default_components

router = APIRouter(prefix="/web", tags=["web"])
templates = Jinja2Templates(directory="app/templates")


async def _get_session_user(request: Request, session: AsyncSession) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    result = await session.execute(select(User).where(User.id == UUID(user_id)))
    return result.scalar_one_or_none()


def _user_is_admin(user: User, settings: Settings) -> bool:
    return user_is_admin(user, settings)


def _device_connection_meta(device: Device, offline_seconds: int):
    return device_connection_meta(device, offline_seconds)


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials"},
            status_code=400,
        )

    set_session_user(request, user, settings)
    return RedirectResponse(url="/web", status_code=303)


@router.get("/register")
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    locale: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Email already registered"},
            status_code=400,
        )

    user = User(email=email, password_hash=get_password_hash(password), locale=locale)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    set_session_user(request, user, settings)
    return RedirectResponse(url="/web", status_code=303)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/web/login", status_code=303)


@router.get("")
async def dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings=Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    result = await session.execute(
        select(Device)
        .options(selectinload(Device.actuators))
        .where(Device.user_id == user.id)
    )
    devices = result.scalars().all()

    claim_message = request.session.pop("claim_message", None)
    dashboard_notice = request.session.pop("dashboard_notice", None)
    device_rows = [
        {"device": device, **device_connection_meta(device, settings.device_offline_seconds)}
        for device in devices
    ]
    context = {
        "request": request,
        "devices": device_rows,
        "claim_message": claim_message,
        "dashboard_notice": dashboard_notice,
        "device_status_poll_interval": settings.device_offline_seconds // 2 or 10,
    }
    return templates.TemplateResponse("dashboard.html", context)


@router.get("/admin")
async def admin_panel(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)
    if not user_is_admin(user, settings):
        return RedirectResponse(url="/web", status_code=303)

    devices_result = await session.execute(
        select(Device)
        .options(selectinload(Device.owner), selectinload(Device.sensors), selectinload(Device.actuators))
        .order_by(Device.created_at.desc())
    )
    devices = devices_result.scalars().all()
    unclaimed = [device for device in devices if device.user_id is None]
    device_cards = [
        {
            "device": device,
            "owner_email": device.owner.email if device.owner else None,
            "connection": _device_connection_meta(device, settings.device_offline_seconds),
            "sensor_count": len(device.sensors or []),
            "actuator_count": len(device.actuators or []),
        }
        for device in devices
    ]
    admin_flash = request.session.pop("admin_flash", None)
    telegram_token = await get_setting(session, "telegram_bot_token")
    apk_meta = await get_apk_metadata(session)
    context = {
        "request": request,
        "unclaimed": unclaimed,
        "admin_flash": admin_flash,
        "devices": device_cards,
        "telegram_bot_token": telegram_token or "",
        "apk_meta": apk_meta,
    }
    return templates.TemplateResponse("admin.html", context)


@router.post("/admin/devices")
async def admin_provision_device(
    request: Request,
    name: str = Form(...),
    model: str | None = Form(None),
    owner_email: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)
    if not _user_is_admin(user, settings):
        return RedirectResponse(url="/web", status_code=303)

    owner_id = None
    owner_email = owner_email.strip() if owner_email else None
    if owner_email:
        result = await session.execute(select(User).where(User.email == owner_email))
        owner = result.scalar_one_or_none()
        if owner is None:
            request.session["admin_flash"] = {"status": "error", "text": f"No user with email {owner_email}"}
            return RedirectResponse(url="/web/admin", status_code=303)
        owner_id = owner.id

    secret = secrets.token_urlsafe(24)
    device = Device(name=name, model=model, user_id=owner_id, secret=secret)
    session.add(device)
    sensors, actuators = await ensure_default_components(session, device)
    await session.commit()
    await session.refresh(device)

    base_url = str(request.base_url).rstrip("/")
    base_url = str(request.base_url).rstrip("/")
    config_snippet = json.dumps(
        {
            "api_base_url": base_url,
            "device_id": str(device.id),
            "device_secret": secret,
            "sensor_ids": {sensor.type.value: str(sensor.id) for sensor in sensors},
            "actuator_ids": {actuator.type.value: str(actuator.id) for actuator in actuators},
        },
        indent=2,
    )
    request.session["admin_flash"] = {
        "status": "success",
        "text": f"Device {device.name} created",
        "device_id": str(device.id),
        "secret": secret,
        "config": config_snippet,
    }
    return RedirectResponse(url="/web/admin", status_code=303)


@router.post("/admin/settings/telegram")
async def admin_update_telegram(
    request: Request,
    bot_token: str = Form(""),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)
    if not _user_is_admin(user, settings):
        return RedirectResponse(url="/web", status_code=303)

    token = bot_token.strip()
    if token:
        await set_setting(session, "telegram_bot_token", token)
        request.session["admin_flash"] = {"status": "success", "text": "Telegram bot token updated."}
    else:
        await delete_setting(session, "telegram_bot_token")
        request.session["admin_flash"] = {"status": "success", "text": "Telegram bot token removed."}
    return RedirectResponse(url="/web/admin", status_code=303)


@router.post("/admin/mobile-apk")
async def admin_upload_mobile_apk(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)
    if not _user_is_admin(user, settings):
        return RedirectResponse(url="/web", status_code=303)

    filename = file.filename or "app.apk"
    if not filename.lower().endswith(".apk"):
        request.session["admin_flash"] = {"status": "error", "text": "Please upload an .apk file."}
        return RedirectResponse(url="/web/admin", status_code=303)

    APK_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    stored_path = APK_DIR / f"plant-app-{timestamp}.apk"
    contents = await file.read()
    stored_path.write_bytes(contents)

    meta = await save_apk_metadata(session, path=stored_path, original_name=Path(filename).name)
    size_kb = len(contents) / 1024
    request.session["admin_flash"] = {
        "status": "success",
        "text": f"Uploaded {Path(filename).name} ({size_kb:.1f} KB) at {meta.get('uploaded_at')}",
    }
    return RedirectResponse(url="/web/admin", status_code=303)


@router.post("/devices/claim")
async def claim_device_form(
    request: Request,
    device_id: str = Form(...),
    device_secret: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        device_uuid = UUID(device_id.strip())
    except ValueError:
        request.session["claim_message"] = {"status": "error", "text": "Device ID must be a valid UUID"}
        return RedirectResponse(url="/web", status_code=303)

    result = await session.execute(select(Device).where(Device.id == device_uuid))
    device = result.scalar_one_or_none()
    if device is None or device.secret != device_secret:
        request.session["claim_message"] = {"status": "error", "text": "Invalid device credentials"}
        return RedirectResponse(url="/web", status_code=303)
    if device.user_id and device.user_id != user.id:
        request.session["claim_message"] = {"status": "error", "text": "Device is already linked to another account"}
        return RedirectResponse(url="/web", status_code=303)

    device.user_id = user.id
    session.add(device)
    await session.commit()
    request.session["claim_message"] = {"status": "success", "text": f"{device.name} linked to your account"}
    return RedirectResponse(url="/web", status_code=303)


@router.post("/devices/{device_id}/delete")
async def delete_device(
    request: Request,
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    device = await _load_device(session, device_id, user)
    if device is None:
        request.session["dashboard_notice"] = {"status": "error", "text": "Device not found or not owned."}
        return RedirectResponse(url="/web", status_code=303)

    await session.delete(device)
    await session.commit()
    request.session["dashboard_notice"] = {"status": "success", "text": f"{device.name} removed."}
    return RedirectResponse(url="/web", status_code=303)


async def _load_device(session: AsyncSession, device_id: UUID, user: User) -> Device | None:
    result = await session.execute(
        select(Device)
        .options(
            selectinload(Device.automation_profile),
            selectinload(Device.actuators),
        )
        .where(Device.id == device_id, Device.user_id == user.id)
    )
    return result.scalar_one_or_none()


@router.get("/devices/statuses")
async def devices_status_api(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings=Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.actuators))
        .where(Device.user_id == user.id)
    )
    devices = result.scalars().all()
    payload = {
        str(device.id): _device_connection_meta(device, settings.device_offline_seconds)
        for device in devices
    }
    return JSONResponse(payload)


@router.get("/devices/{device_id}")
async def view_device(
    request: Request,
    device_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    settings=Depends(get_app_settings),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    device = await _load_device(session, device_id, user)
    if device is None:
        return RedirectResponse(url="/web", status_code=303)
    sensors = (await session.execute(select(Sensor).where(Sensor.device_id == device.id))).scalars().all()
    readings: dict[Any, dict[str, Any] | None] = {}
    for sensor in sensors:
        result = await session.execute(
            select(SensorReading)
            .where(SensorReading.sensor_id == sensor.id)
            .order_by(SensorReading.recorded_at.desc())
            .limit(1)
        )
        reading = result.scalar_one_or_none()
        if reading is None:
            readings[sensor.id] = None
        else:
            label, _ = time_since(reading.recorded_at)
            readings[sensor.id] = {
                "value": reading.value_numeric,
                "recorded": label,
            }

    profile = device.automation_profile
    alerts = (
        await session.execute(
            select(Alert)
            .where(Alert.device_id == device.id)
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    lamp_schedule = profile.lamp_schedule if profile and profile.lamp_schedule else {}
    flash_message = request.session.pop("flash_message", None)
    context = {
        "request": request,
        "device": device,
        "sensors": sensors,
        "readings": readings,
        "profile": profile,
        "actuators": device.actuators,
        "device_status": _device_connection_meta(device, settings.device_offline_seconds),
        "device_status_poll_interval": settings.device_offline_seconds // 2 or 10,
        "alerts": alerts,
        "lamp_schedule": lamp_schedule,
        "flash_message": flash_message,
    }
    return templates.TemplateResponse("device_detail.html", context)


@router.post("/devices/{device_id}/automation")
async def save_automation_profile(
    request: Request,
    device_id: UUID,
    soil_moisture_min: float = Form(...),
    soil_moisture_max: float = Form(...),
    temp_min: float = Form(...),
    temp_max: float = Form(...),
    min_water_level: float = Form(20),
    watering_duration_sec: int = Form(20),
    watering_cooldown_min: int = Form(60),
    lamp_on_minutes: str | None = Form(None),
    lamp_off_minutes: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    device = await _load_device(session, device_id, user)
    if device is None:
        return RedirectResponse(url="/web", status_code=303)
    profile = device.automation_profile or AutomationProfile(device_id=device.id)
    profile.soil_moisture_min = soil_moisture_min
    profile.soil_moisture_max = soil_moisture_max
    profile.temp_min = temp_min
    profile.temp_max = temp_max
    profile.min_water_level = min_water_level
    profile.watering_duration_sec = watering_duration_sec
    profile.watering_cooldown_min = watering_cooldown_min
    try:
        on_minutes_val = int(lamp_on_minutes) if lamp_on_minutes else None
        off_minutes_val = int(lamp_off_minutes) if lamp_off_minutes else None
    except ValueError:
        request.session["flash_message"] = "Light schedule values must be numbers"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)
    if on_minutes_val and off_minutes_val:
        profile.lamp_schedule = {"on_minutes": on_minutes_val, "off_minutes": off_minutes_val}
    else:
        profile.lamp_schedule = None
    session.add(profile)
    await session.commit()
    request.session["flash_message"] = "Automation profile updated"
    return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)


@router.post("/devices/{device_id}/commands")
async def manual_command(
    request: Request,
    device_id: UUID,
    actuator_id: UUID = Form(...),
    command: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
):
    user = await _get_session_user(request, session)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    device = await _load_device(session, device_id, user)
    if device is None:
        return RedirectResponse(url="/web", status_code=303)

    actuator = next((act for act in device.actuators if act.id == actuator_id), None)
    if actuator is None:
        request.session["flash_message"] = "Unknown actuator"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)

    try:
        command_type = CommandType(command.lower())
    except ValueError:
        request.session["flash_message"] = "Unsupported command"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)

    cmd = Command(device_id=device.id, actuator_id=actuator.id, command=command_type, payload=None)
    session.add(cmd)
    await session.commit()
    request.session["flash_message"] = f"Command {command_type.value} sent to {actuator.type.value}"
    return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)
