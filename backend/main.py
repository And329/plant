from fastapi import FastAPI

from app.app_factory import create_base_app
from app.routers.groups import API_ROUTERS


def create_app() -> FastAPI:
    app = create_base_app()
    for router in API_ROUTERS:
        app.include_router(router)
    return app


app = create_app()
