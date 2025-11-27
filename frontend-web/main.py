from fastapi import FastAPI

# Import from backend package
from app.app_factory import create_base_app

# Import local web routers
from app.routers.groups import WEB_ROUTERS


def create_app() -> FastAPI:
    app = create_base_app()
    for router in WEB_ROUTERS:
        app.include_router(router)
    return app


app = create_app()
