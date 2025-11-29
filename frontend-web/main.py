"""Refactored main entry point for frontend-web service using HTTP API."""
from fastapi import FastAPI

from app.app_factory import create_app
from app.routers.groups import FRONTEND_ROUTERS


def build_app() -> FastAPI:
    """Build and configure the web frontend application.

    Returns:
        Configured FastAPI application
    """
    app = create_app()

    # Include all frontend routers
    for router in FRONTEND_ROUTERS:
        app.include_router(router)

    return app


app = build_app()
