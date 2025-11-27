from fastapi import APIRouter

from . import landing, web

WEB_ROUTERS: tuple[APIRouter, ...] = (
    landing.router,
    web.router,
)

__all__ = ["WEB_ROUTERS"]
