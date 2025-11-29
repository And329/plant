"""FastAPI application factory for frontend-web service."""
import os

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def create_app() -> FastAPI:
    """Create FastAPI application with middleware for web frontend.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(title="Plant Automation Web UI")

    # Session middleware for storing JWT tokens
    session_secret = os.getenv("SESSION_SECRET_KEY", "dev-secret-change-in-production")
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        session_cookie="plant_session",
    )

    # Proxy headers middleware for correct client IP detection
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    return app
