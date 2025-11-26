from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qsl
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import verify_password
from app.deps import get_app_settings, get_db_session
from app.models.entities import Device, User
from app.routers.web import _device_connection_meta, _set_session_user
from app.services.app_settings import get_setting

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/telegram", tags=["telegram"], include_in_schema=False)
logger = logging.getLogger("telegram-webapp")


async def _require_bot_token(session: AsyncSession) -> str:
    token = await get_setting(session, "telegram_bot_token")
    if not token:
        raise HTTPException(status_code=503, detail="Telegram integration not configured")
    return token


def _verify_init_data(init_data: str, bot_token: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=400, detail="Missing init data")
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    hash_value = parsed.pop("hash", None)
    if not hash_value:
        logger.warning("Telegram init data missing hash.")
        raise HTTPException(status_code=400, detail="Invalid init data")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if signature != hash_value:
        logger.warning("Telegram init data bad signature.")
        raise HTTPException(status_code=400, detail="Bad signature")
    if "user" not in parsed:
        logger.warning("Telegram init data missing user payload.")
        raise HTTPException(status_code=400, detail="No user payload")
    try:
        return json.loads(parsed["user"])
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed user payload") from None


async def _get_user_from_session(request: Request, session: AsyncSession) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    result = await session.execute(select(User).where(User.id == UUID(user_id)))
    return result.scalar_one_or_none()


@router.get("")
async def telegram_webapp(request: Request):
    return templates.TemplateResponse("telegram_app.html", {"request": request})


@router.post("/session")
async def telegram_session(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    payload = await request.json()
    init_data = payload.get("init_data", "")
    if not init_data:
        logger.warning("Telegram session init data missing. Payload=%r", payload)
    try:
        bot_token = await _require_bot_token(session)
    except HTTPException as exc:
        return JSONResponse({"status": "disabled", "detail": exc.detail}, status_code=exc.status_code)

    telegram_user = _verify_init_data(init_data, bot_token)
    request.session["telegram_user"] = telegram_user

    result = await session.execute(select(User).where(User.telegram_id == str(telegram_user["id"])))
    linked_user = result.scalar_one_or_none()
    if linked_user:
        _set_session_user(request, linked_user, settings)
        return {"status": "linked"}
    return {"status": "unlinked", "telegram_user": telegram_user}


@router.post("/link")
async def telegram_link(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    payload = await request.json()
    init_data = payload.get("init_data", "")
    email = payload.get("email", "")
    password = payload.get("password", "")
    bot_token = await _require_bot_token(session)
    telegram_user = _verify_init_data(init_data, bot_token)

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")

    user.telegram_id = str(telegram_user["id"])
    session.add(user)
    await session.commit()
    _set_session_user(request, user, settings)
    request.session["telegram_user"] = telegram_user
    return {"status": "linked"}


@router.get("/devices")
async def telegram_devices(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    user = await _get_user_from_session(request, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not linked")
    result = await session.execute(select(Device).where(Device.user_id == user.id))
    devices = result.scalars().all()
    payload = [
        {
            "id": str(device.id),
            "name": device.name,
            "model": device.model,
            **_device_connection_meta(device, settings.device_offline_seconds),
        }
        for device in devices
    ]
    return {"devices": payload}
