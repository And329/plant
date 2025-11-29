"""Router groups for web frontend."""
from fastapi import APIRouter

from . import landing, web

# All frontend routers
FRONTEND_ROUTERS: tuple[APIRouter, ...] = (
    landing.router,
    web.router,
)

__all__ = ["FRONTEND_ROUTERS"]
