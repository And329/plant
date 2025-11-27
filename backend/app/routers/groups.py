from fastapi import APIRouter

from . import alerts, auth, commands, devices, landing, telegram_webapp, telemetry, users, web

API_ROUTERS: tuple[APIRouter, ...] = (
    auth.router,
    telemetry.router,
    commands.router,
    devices.router,
    alerts.router,
    users.router,
)

WEB_ROUTERS: tuple[APIRouter, ...] = (
    landing.router,
    web.router,
)

TELEGRAM_ROUTERS: tuple[APIRouter, ...] = (telegram_webapp.router,)

ALL_ROUTERS: tuple[APIRouter, ...] = API_ROUTERS + WEB_ROUTERS + TELEGRAM_ROUTERS

__all__ = ["API_ROUTERS", "WEB_ROUTERS", "TELEGRAM_ROUTERS", "ALL_ROUTERS"]
