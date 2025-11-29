"""Refactored web UI router using HTTP API client instead of direct database access."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api_client import get_api_client

router = APIRouter(prefix="/web", tags=["web"])
templates = Jinja2Templates(directory="app/templates")

# Get backend API URL from environment
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://api:8000")
DEVICE_OFFLINE_SECONDS = int(os.getenv("DEVICE_OFFLINE_SECONDS", "120"))


def _load_admin_emails() -> list[str]:
    """Load admin emails from env (supports JSON array or comma-separated)."""
    raw = os.getenv("PLANT_ADMIN_EMAILS") or os.getenv("ADMIN_EMAILS") or ""
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [
                item.strip() for item in value if isinstance(item, str) and item.strip()
            ]
    except json.JSONDecodeError:
        pass
    return [item.strip() for item in raw.split(",") if item.strip()]


ADMIN_EMAILS = _load_admin_emails()


def _get_api_client():
    """Get API client instance."""
    return get_api_client(BACKEND_API_URL)


def _is_authenticated(request: Request) -> bool:
    """Check if user is authenticated."""
    return bool(request.session.get("access_token"))


def _is_admin(request: Request) -> bool:
    """Check if user is admin."""
    return request.session.get("is_admin", False)


def _time_since(moment_iso: str | None) -> tuple[str, int | None]:
    """Calculate time since a timestamp."""
    if not moment_iso:
        return ("never", None)

    moment = datetime.fromisoformat(moment_iso.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
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


def _device_connection_meta(device: dict, offline_seconds: int) -> dict:
    """Get device connection status metadata."""
    last_seen_label, seconds = _time_since(device.get("last_seen"))
    connected = seconds is not None and seconds <= offline_seconds

    return {
        "status": "connected" if connected else "disconnected",
        "last_seen": last_seen_label,
        "connected": connected,
        "last_seen_iso": device.get("last_seen"),
    }


@router.get("/login")
async def login_form(request: Request):
    """Show login form."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Handle login form submission."""
    client = _get_api_client()

    try:
        auth_response = await client.login(email, password)

        # Store tokens in session
        request.session["access_token"] = auth_response["access_token"]
        request.session["refresh_token"] = auth_response["refresh_token"]
        request.session["user_id"] = auth_response["user"]["id"]
        request.session["user_email"] = auth_response["user"]["email"]
        request.session["is_admin"] = auth_response["user"]["email"] in ADMIN_EMAILS

        return RedirectResponse(url="/web", status_code=303)

    except httpx.HTTPStatusError:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid credentials"},
            status_code=400,
        )


@router.get("/register")
async def register_form(request: Request):
    """Show registration form."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    locale: str | None = Form(None),
):
    """Handle registration form submission."""
    client = _get_api_client()

    try:
        # Register user
        await client.register(email, password, locale)

        # Login immediately
        auth_response = await client.login(email, password)

        # Store tokens in session
        request.session["access_token"] = auth_response["access_token"]
        request.session["refresh_token"] = auth_response["refresh_token"]
        request.session["user_id"] = auth_response["user"]["id"]
        request.session["user_email"] = auth_response["user"]["email"]
        request.session["is_admin"] = auth_response["user"]["email"] in ADMIN_EMAILS

        return RedirectResponse(url="/web", status_code=303)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_msg = "Email already registered"
        elif e.response.status_code == 422:
            error_msg = "Invalid input. Password must be at least 8 characters."
        else:
            error_msg = "Registration failed"
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": error_msg},
            status_code=400,
        )


@router.get("/logout")
async def logout(request: Request):
    """Logout user."""
    request.session.clear()
    return RedirectResponse(url="/web/login", status_code=303)


@router.get("")
async def dashboard(request: Request):
    """Show dashboard with user's devices."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)

    client = _get_api_client()

    try:
        devices = await client.list_devices(request)

        claim_message = request.session.pop("claim_message", None)
        dashboard_notice = request.session.pop("dashboard_notice", None)

        device_rows = [
            {
                "device": device,
                **_device_connection_meta(device, DEVICE_OFFLINE_SECONDS),
            }
            for device in devices
        ]

        context = {
            "request": request,
            "devices": device_rows,
            "claim_message": claim_message,
            "dashboard_notice": dashboard_notice,
            "device_status_poll_interval": DEVICE_OFFLINE_SECONDS // 2 or 10,
        }
        return templates.TemplateResponse("dashboard.html", context)

    except httpx.HTTPStatusError:
        request.session.clear()
        return RedirectResponse(url="/web/login", status_code=303)


@router.get("/admin")
async def admin_panel(request: Request):
    """Show admin panel."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)
    if not _is_admin(request):
        return RedirectResponse(url="/web", status_code=303)

    client = _get_api_client()

    try:
        devices = await client.list_devices(request)
        device_configs = {}
        for device in devices:
            try:
                cfg = await client.get_device_config(UUID(device["id"]), request)
                device_configs[device["id"]] = cfg
            except httpx.HTTPStatusError:
                device_configs[device["id"]] = None

        admin_flash = request.session.pop("admin_flash", None)

        # Shape device data for the template (flattened to avoid template errors)
        device_cards = []
        for device in devices:
            connection = _device_connection_meta(device, DEVICE_OFFLINE_SECONDS)
            cfg = device_configs.get(device["id"])
            config_snippet = None
            if cfg:
                config_body = {
                    "api_base_url": BACKEND_API_URL.rstrip("/"),
                    "device_id": cfg["device_id"],
                    "device_secret": "<secret from provisioning time>",
                    "sensor_ids": cfg.get("sensor_ids", {}),
                    "actuator_ids": cfg.get("actuator_ids", {}),
                }
                config_snippet = json.dumps(config_body, indent=2)
            device_cards.append(
                {
                    "id": device.get("id"),
                    "name": device.get("name"),
                    "model": device.get("model"),
                    "created_at": device.get("created_at", ""),
                    "owner_email": request.session.get("user_email"),
                    "connection": connection,
                    "sensor_count": len(device.get("sensors", [])),
                    "actuator_count": len(device.get("actuators", [])),
                    "config_snippet": config_snippet,
                }
            )

        context = {
            "request": request,
            "admin_flash": admin_flash,
            "devices": device_cards,
            "unclaimed": [],
            "telegram_bot_token": "",  # TODO: Add settings API
        }
        return templates.TemplateResponse("admin.html", context)

    except httpx.HTTPStatusError:
        request.session.clear()
        return RedirectResponse(url="/web/login", status_code=303)


@router.post("/admin/devices")
async def admin_provision_device(
    request: Request,
    name: str = Form(...),
    model: str | None = Form(None),
    owner_email: str | None = Form(None),
):
    """Provision a new device (admin only)."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)
    if not _is_admin(request):
        return RedirectResponse(url="/web", status_code=303)

    client = _get_api_client()

    try:
        # Leave devices unassigned by default - users must claim them
        assign_to_self = False
        device_response = await client.create_device(
            name, request, model, owner_email, assign_to_self
        )

        # Build config snippet for device
        base_url = BACKEND_API_URL.rstrip("/")
        config_body = {
            "api_base_url": base_url,
            "device_id": device_response["device"]["id"],
            "device_secret": device_response["secret"],
        }
        if device_response.get("sensor_ids"):
            config_body["sensor_ids"] = device_response["sensor_ids"]
        if device_response.get("actuator_ids"):
            config_body["actuator_ids"] = device_response["actuator_ids"]
        config_snippet = json.dumps(config_body, indent=2)

        request.session["admin_flash"] = {
            "status": "success",
            "text": f"Device {name} created",
            "device_id": device_response["device"]["id"],
            "secret": device_response["secret"],
            "config": config_snippet,
        }
        return RedirectResponse(url="/web/admin", status_code=303)

    except httpx.HTTPStatusError as e:
        error_msg = "Failed to create device"
        if e.response.status_code == 400:
            error_msg = "Invalid request"
        request.session["admin_flash"] = {"status": "error", "text": error_msg}
        return RedirectResponse(url="/web/admin", status_code=303)


@router.post("/admin/devices/{device_id}/delete")
async def admin_delete_device(request: Request, device_id: UUID):
    """Delete a device (admin only)."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)
    if not _is_admin(request):
        return RedirectResponse(url="/web", status_code=303)

    client = _get_api_client()
    try:
        await client.delete_device(device_id, request)
        request.session["admin_flash"] = {
            "status": "success",
            "text": "Device deleted.",
        }
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        msg = "Failed to delete device"
        if status == 404:
            msg = "Device not found"
        request.session["admin_flash"] = {"status": "error", "text": msg}
    return RedirectResponse(url="/web/admin", status_code=303)


@router.post("/admin/settings/telegram")
async def admin_update_telegram(request: Request, bot_token: str = Form("")):
    """Placeholder for Telegram bot token management (no backend endpoint yet)."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)
    if not _is_admin(request):
        return RedirectResponse(url="/web", status_code=303)

    token = bot_token.strip()
    if token:
        request.session["admin_flash"] = {
            "status": "success",
            "text": "Telegram bot token saved locally (no backend persistence yet).",
        }
    else:
        request.session["admin_flash"] = {
            "status": "success",
            "text": "Telegram bot token cleared locally (no backend persistence yet).",
        }
    return RedirectResponse(url="/web/admin", status_code=303)


@router.post("/devices/claim")
async def claim_device_form(
    request: Request,
    device_id: str = Form(...),
    device_secret: str = Form(...),
):
    """Claim a device to user account."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)

    client = _get_api_client()

    try:
        device_uuid = UUID(device_id.strip())
    except ValueError:
        request.session["claim_message"] = {
            "status": "error",
            "text": "Device ID must be a valid UUID",
        }
        return RedirectResponse(url="/web", status_code=303)

    try:
        device = await client.claim_device(device_uuid, device_secret, request)
        request.session["claim_message"] = {
            "status": "success",
            "text": f"{device['name']} linked to your account",
        }
        return RedirectResponse(url="/web", status_code=303)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            error_msg = "Invalid device credentials"
        elif e.response.status_code == 409:
            error_msg = "Device is already linked to another account"
        else:
            error_msg = "Failed to claim device"

        request.session["claim_message"] = {"status": "error", "text": error_msg}
        return RedirectResponse(url="/web", status_code=303)


@router.get("/devices/statuses")
async def devices_status_api(request: Request):
    """Get device connection statuses (AJAX endpoint)."""
    if not _is_authenticated(request):
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})

    client = _get_api_client()

    try:
        devices = await client.list_devices(request)
        payload = {
            device["id"]: _device_connection_meta(device, DEVICE_OFFLINE_SECONDS)
            for device in devices
        }
        return JSONResponse(payload)

    except httpx.HTTPStatusError:
        return JSONResponse(status_code=401, content={"detail": "Not authenticated"})


@router.get("/devices/{device_id}")
async def view_device(request: Request, device_id: UUID):
    """View device details."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)

    client = _get_api_client()

    try:
        device = await client.get_device(device_id, request)
        telemetry = await client.get_latest_readings(device_id, request)
        alerts = await client.list_alerts(request, device_id)

        # Format readings
        readings = {}
        for reading in telemetry.get("readings", []):
            sensor_id = reading["sensor_id"]
            label, _ = _time_since(reading.get("timestamp"))
            readings[sensor_id] = {
                "value": reading["value"],
                "recorded": label,
            }

        # Get automation profile
        profile = device.get("automation_profile")
        lamp_schedule = profile.get("lamp_schedule", {}) if profile else {}

        flash_message = request.session.pop("flash_message", None)

        context = {
            "request": request,
            "device": device,
            "sensors": device.get("sensors", []),
            "readings": readings,
            "profile": profile,
            "actuators": device.get("actuators", []),
            "device_status": _device_connection_meta(device, DEVICE_OFFLINE_SECONDS),
            "device_status_poll_interval": DEVICE_OFFLINE_SECONDS // 2 or 10,
            "alerts": alerts[:10],  # Limit to 10 most recent
            "lamp_schedule": lamp_schedule,
            "flash_message": flash_message,
        }
        return templates.TemplateResponse("device_detail.html", context)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return RedirectResponse(url="/web", status_code=303)
        request.session.clear()
        return RedirectResponse(url="/web/login", status_code=303)


@router.post("/devices/{device_id}/automation")
async def save_automation_profile(
    request: Request,
    device_id: UUID,
    soil_moisture_min: float | None = Form(None),
    soil_moisture_max: float | None = Form(None),
    temp_min: float | None = Form(None),
    temp_max: float | None = Form(None),
    min_water_level: float | None = Form(None),
    watering_duration_sec: int | None = Form(None),
    watering_cooldown_min: int | None = Form(None),
    lamp_on_minutes: str | None = Form(None),
    lamp_off_minutes: str | None = Form(None),
):
    """Save automation profile for device."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)

    client = _get_api_client()

    profile_data = {}
    if soil_moisture_min is not None and soil_moisture_min != "":
        profile_data["soil_moisture_min"] = float(soil_moisture_min)
    if soil_moisture_max is not None and soil_moisture_max != "":
        profile_data["soil_moisture_max"] = float(soil_moisture_max)
    if temp_min is not None and temp_min != "":
        profile_data["temp_min"] = float(temp_min)
    if temp_max is not None and temp_max != "":
        profile_data["temp_max"] = float(temp_max)
    if min_water_level is not None and min_water_level != "":
        profile_data["min_water_level"] = float(min_water_level)
    if watering_duration_sec is not None and watering_duration_sec != "":
        profile_data["watering_duration_sec"] = int(watering_duration_sec)
    if watering_cooldown_min is not None and watering_cooldown_min != "":
        profile_data["watering_cooldown_min"] = int(watering_cooldown_min)

    # Handle lamp schedule
    try:
        on_minutes_val = int(lamp_on_minutes) if lamp_on_minutes else None
        off_minutes_val = int(lamp_off_minutes) if lamp_off_minutes else None
    except ValueError:
        request.session["flash_message"] = "Light schedule values must be numbers"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)

    if on_minutes_val is not None and off_minutes_val is not None:
        profile_data["lamp_schedule"] = {
            "on_minutes": on_minutes_val,
            "off_minutes": off_minutes_val,
        }
    elif on_minutes_val is not None or off_minutes_val is not None:
        profile_data["lamp_schedule"] = None

    try:
        await client.update_automation_profile(device_id, request, **profile_data)
        request.session["flash_message"] = "Automation profile updated"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)

    except httpx.HTTPStatusError:
        request.session["flash_message"] = "Failed to update automation profile"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)


@router.post("/devices/{device_id}/commands")
async def manual_command(
    request: Request,
    device_id: UUID,
    actuator_id: UUID = Form(...),
    command: str = Form(...),
):
    """Send manual command to device."""
    if not _is_authenticated(request):
        return RedirectResponse(url="/web/login", status_code=303)

    client = _get_api_client()

    try:
        command_type = command.lower()
        await client.send_command(device_id, actuator_id, command_type, request)
        request.session["flash_message"] = f"Command {command_type} sent"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)

    except httpx.HTTPStatusError:
        request.session["flash_message"] = "Failed to send command"
        return RedirectResponse(url=f"/web/devices/{device_id}", status_code=303)
