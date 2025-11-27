from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import create_access_token, decode_token, verify_password
from app.deps import get_app_settings, get_db_session
from app.models.entities import Device, User
from app.schemas.auth import (
    DeviceAuthRequest,
    DeviceAuthResponse,
    DeviceTokenResponse,
    RefreshRequest,
    TokenPair,
    UserTokenResponse,
)
from app.schemas.device import AutomationProfileOut
from app.schemas.user import UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(*, subject: str, scope: str, settings: Settings, claims: dict[str, str]) -> TokenPair:
    now = datetime.now(timezone.utc)
    access_expires = timedelta(minutes=settings.access_token_expire_minutes)
    refresh_expires = timedelta(minutes=settings.refresh_token_expire_minutes)

    access_token = create_access_token(
        subject=subject,
        expires_delta=access_expires,
        scope=scope,
        token_type="access",
        **claims,
    )
    refresh_token = create_access_token(
        subject=subject,
        expires_delta=refresh_expires,
        scope=scope,
        token_type="refresh",
        **claims,
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=now + access_expires,
    )


def _build_device_tokens(device: Device, settings: Settings) -> DeviceTokenResponse:
    pair = _issue_tokens(
        subject=str(device.id),
        scope="device",
        settings=settings,
        claims={"device_id": str(device.id)},
    )
    return DeviceTokenResponse(**pair.model_dump())


def _build_user_tokens(user: User, settings: Settings) -> TokenPair:
    return _issue_tokens(
        subject=str(user.id),
        scope="user",
        settings=settings,
        claims={"user_id": str(user.id)},
    )


@router.post("/device", response_model=DeviceAuthResponse)
async def authenticate_device(
    payload: DeviceAuthRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    result = await session.execute(
        select(Device)
            .options(selectinload(Device.automation_profile))
            .where(Device.id == payload.device_id)
    )
    device: Device | None = result.scalar_one_or_none()
    if device is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown device")

    if not verify_password(payload.device_secret, device.secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

    tokens = _build_device_tokens(device, settings)
    automation_profile = (
        AutomationProfileOut.model_validate(device.automation_profile).model_dump()
        if device.automation_profile
        else None
    )
    return DeviceAuthResponse(
        **tokens.model_dump(),
        device={"id": device.id, "name": device.name},
        automation_profile=automation_profile,
    )


@router.post("/login", response_model=UserTokenResponse)
async def login(
    payload: UserLogin,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    tokens = _build_user_tokens(user, settings)
    return UserTokenResponse(**tokens.model_dump(), user=UserOut.model_validate(user))


async def _refresh_tokens(
    payload: RefreshRequest,
    session: AsyncSession,
    settings: Settings,
    expected_scope: str | None = None,
) -> TokenPair:
    try:
        decoded = decode_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None

    if decoded.get("token_type") != "refresh":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wrong token type")

    scope = decoded.get("scope")
    if expected_scope and scope != expected_scope:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unexpected token scope")

    subject_id = decoded.get("sub")
    if scope == "device":
        result = await session.execute(select(Device).where(Device.id == UUID(subject_id)))
        device = result.scalar_one_or_none()
        if device is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
        return _build_device_tokens(device, settings)
    if scope == "user":
        result = await session.execute(select(User).where(User.id == UUID(subject_id)))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return _build_user_tokens(user, settings)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported token scope")


@router.post("/device/refresh", response_model=DeviceTokenResponse)
async def refresh_device_token(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    tokens = await _refresh_tokens(payload, session, settings, expected_scope="device")
    return DeviceTokenResponse(**tokens.model_dump())


@router.post("/refresh", response_model=TokenPair)
async def refresh_any_token(
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    return await _refresh_tokens(payload, session, settings)
