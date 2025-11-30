from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import os

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["site"], include_in_schema=False)
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://api:8000")


@router.get("/")
async def landing_page(request: Request):
    features = [
        {
            "title": "Real-time telemetry",
            "body": "Stream moisture, temperature, and water-level readings into a unified dashboard from every planter you ship.",
        },
        {
            "title": "Remote control",
            "body": "Queue pump and lighting commands, pulse actuators, and track acknowledgement without SSH-ing into a device.",
        },
        {
            "title": "Automation profiles",
            "body": "Set watering thresholds, light schedules, and alerting rules per device — the worker handles execution for you.",
        },
    ]
    steps = [
        "Provision a device from the Admin console to generate secrets and sensor IDs.",
        "Flash the Pi client config onto new hardware and plug it into your planter.",
        "Claim the planter or ship it unclaimed — the end user links it with a single secret.",
    ]
    context = {
        "request": request,
        "features": features,
        "steps": steps,
        "backend_base": BACKEND_API_URL.rstrip("/"),
    }
    return templates.TemplateResponse("landing.html", context)


@router.get("/app-download")
async def app_download(request: Request):
    """Public mobile app download page (links to backend-served APK)."""
    context = {
        "request": request,
        "backend_base": BACKEND_API_URL.rstrip("/"),
    }
    return templates.TemplateResponse("app_download.html", context)
