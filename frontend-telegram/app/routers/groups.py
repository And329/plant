from fastapi import APIRouter

from . import telegram_webapp

TELEGRAM_ROUTERS: tuple[APIRouter, ...] = (telegram_webapp.router,)

__all__ = ["TELEGRAM_ROUTERS"]
