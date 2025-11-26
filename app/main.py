from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.deps import automation_engine
from app.routers import alerts, auth, commands, devices, landing, telegram_webapp, telemetry, users, web


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover - wiring
    try:
        yield
    finally:
        await automation_engine.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret_key,
        session_cookie="plant_session",
    )
    app.include_router(auth.router)
    app.include_router(telemetry.router)
    app.include_router(commands.router)
    app.include_router(devices.router)
    app.include_router(landing.router)
    app.include_router(telegram_webapp.router)
    app.include_router(alerts.router)
    app.include_router(users.router)
    app.include_router(web.router)
    return app


app = create_app()
