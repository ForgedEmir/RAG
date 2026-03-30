"""Router admin — /api/admin/*"""
import logging
import os

from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse

from src.api.auth import require_monitoring
from src.api.limiter import limiter
from src.monitoring.tracker import track
from src.security.validator import valider_entree

logger = logging.getLogger(__name__)
admin_router = APIRouter()

_MAX_UPLOAD   = int(os.getenv("MAX_UPLOAD_SIZE_KB", "500")) * 1024
_ALLOWED_EXT  = {".txt", ".md", ".csv", ".json", ".xml", ".xlsx"}
_DATA_DIR     = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample"))


@admin_router.get("/api/admin/sources")
async def admin_sources(request: Request):
    require_monitoring(request)
    from src.ingestion.run import list_current_files
    fichiers = list_current_files()
    return {"files": sorted(fichiers.keys()), "total": len(fichiers)}


@admin_router.post("/api/admin/upload")
@limiter.limit("20/hour")
async def admin_upload(request: Request, file: UploadFile = File(...)):
    require_monitoring(request)

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        return JSONResponse({"error": f"Extension non supportée. Formats : {', '.join(_ALLOWED_EXT)}"}, status_code=400)

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD:
        return JSONResponse({"error": f"Fichier trop volumineux ({len(raw)//1024} Ko). Max : {_MAX_UPLOAD//1024} Ko."}, status_code=400)

    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        return JSONResponse({"error": "Encodage invalide."}, status_code=400)

    lines = text.splitlines()
    mid   = len(lines) // 2
    sample = "\n".join(lines[:20] + lines[max(0, mid-5):mid+5] + lines[-20:]) or text[:2000]

    check = valider_entree(sample)
    if not check["valid"]:
        logger.warning(f"Upload bloqué [{check['type']}] — '{file.filename}'")
        track("upload_blocked", detail=f"{file.filename} | {check['type']}")
        return JSONResponse({"error": "Contenu suspect. Upload refusé."}, status_code=400)

    os.makedirs(_DATA_DIR, exist_ok=True)
    dest = os.path.join(_DATA_DIR, os.path.basename(file.filename or "upload"))
    with open(dest, "wb") as out:
        out.write(raw)

    track("upload", detail=f"{file.filename} | {len(raw)//1024} Ko")
    logger.info(f"Fichier uploadé : {file.filename} ({len(raw)//1024} Ko)")
    return {"message": f"'{file.filename}' uploadé. Lance une réindexation pour l'activer.", "filename": file.filename}


@admin_router.delete("/api/admin/delete")
async def admin_delete(request: Request):
    require_monitoring(request)
    body = await request.json()
    filename = (body or {}).get("filename", "").strip()
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"error": "Nom de fichier invalide"}, status_code=400)
    path = os.path.join(_DATA_DIR, filename)
    if not os.path.exists(path):
        return JSONResponse({"error": "Fichier introuvable"}, status_code=404)
    os.remove(path)
    track("reindex", detail=f"suppression : {filename}")
    logger.info(f"Fichier supprimé : {filename}")
    return {"message": f"'{filename}' supprimé. Réindexe pour mettre à jour Qdrant."}
