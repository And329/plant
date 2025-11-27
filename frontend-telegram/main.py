from fastapi import FastAPI

# Import from backend package
from app.app_factory import create_base_app

# Import local telegram routers
from app.routers.groups import TELEGRAM_ROUTERS


def create_app() -> FastAPI:
    app = create_base_app()
    for router in TELEGRAM_ROUTERS:
        app.include_router(router)
    return app


app = create_app()
