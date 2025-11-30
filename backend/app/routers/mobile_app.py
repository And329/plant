from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.deps import get_app_settings, get_current_user, get_db_session
from app.services.mobile_app import APK_DIR, get_apk_metadata, save_apk_metadata

router = APIRouter(tags=["mobile"])


@router.get("/app-download/meta")
async def apk_meta(session: AsyncSession = Depends(get_db_session)):
    meta = await get_apk_metadata(session)
    if not meta or not meta["exists"]:
        raise HTTPException(status_code=404, detail="No APK available")
    # Return minimal public info
    return {
        "original_name": meta["original_name"],
        "uploaded_at": meta["uploaded_at"],
        "size_bytes": meta["size_bytes"],
        "size_human": meta["size_human"],
    }


@router.get("/app-download/latest")
async def apk_download(session: AsyncSession = Depends(get_db_session)):
    meta = await get_apk_metadata(session)
    if not meta or not meta["exists"]:
        raise HTTPException(status_code=404, detail="No APK available")
    path = Path(meta["path"])
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=meta.get("original_name") or path.name,
    )


@router.post("/admin/mobile-apk")
async def admin_upload_apk(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
    user=Depends(get_current_user),
):
    if user.email not in settings.admin_emails:
        raise HTTPException(status_code=403, detail="Admins only")

    filename = file.filename or "app.apk"
    if not filename.lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="Only .apk files are allowed")

    APK_DIR.mkdir(parents=True, exist_ok=True)
    stored_path = APK_DIR / filename
    contents = await file.read()
    stored_path.write_bytes(contents)

    await save_apk_metadata(session, path=stored_path, original_name=filename)
    return {"detail": "Uploaded", "filename": filename, "size_bytes": len(contents)}
