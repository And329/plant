from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.core.config import get_settings
from app.deps import automation_engine


@asynccontextmanager
async def _lifespan(app: FastAPI):
    try:
        yield
    finally:
        await automation_engine.close()


def create_base_app() -> FastAPI:
    """
    Build a FastAPI application with shared middleware, settings, and lifespan hooks.
    Individual services can include their own routers on top of this base instance.
    """
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=_lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie="plant_session",
    )
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
    return app
