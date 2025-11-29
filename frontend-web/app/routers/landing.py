from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["site"], include_in_schema=False)


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
    }
    return templates.TemplateResponse("landing.html", context)
