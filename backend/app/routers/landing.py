from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.deps import get_db_session
from app.services.mobile_app import APK_DIR, get_apk_metadata

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["site"], include_in_schema=False)


@router.get("/")
async def landing_page(request: Request, session=Depends(get_db_session)):
    if request.session.get("user_id"):
        return RedirectResponse(url="/web", status_code=303)

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
        "apk": await get_apk_metadata(session),
    }
    return templates.TemplateResponse("landing.html", context)


@router.get("/app-download")
async def app_download(request: Request, session=Depends(get_db_session)):
    apk = await get_apk_metadata(session)
    return templates.TemplateResponse(
        "app_download.html",
        {
            "request": request,
            "apk": apk,
        },
    )


@router.get("/app-download/latest")
async def app_download_latest(session=Depends(get_db_session)):
    apk = await get_apk_metadata(session)
    if not apk or not apk["exists"]:
        raise HTTPException(status_code=404, detail="No APK uploaded yet")
    path = Path(apk["path"])
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=apk.get("original_name") or path.name,
    )
