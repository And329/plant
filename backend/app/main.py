from fastapi import FastAPI

from app.app_factory import create_base_app
from app.routers.groups import ALL_ROUTERS


def create_app() -> FastAPI:
    """
    Legacy single-process application that wires every router together.
    Useful for local development, but production runs separate services.
    """
    app = create_base_app()
    for router in ALL_ROUTERS:
        app.include_router(router)
    return app


app = create_app()
