import logging
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from src.api.auth import require_monitoring
from src.monitoring.tracker import track

logger = logging.getLogger(__name__)
admin_router = APIRouter()

DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample"))

@admin_router.get("/api/admin/sources")
async def admin_sources(request: Request):
    require_monitoring(request)
    from src.ingestion.run import list_current_files
    files = list_current_files()
    return {"files": sorted(files.keys()), "total": len(files)}


@admin_router.delete("/api/admin/delete")
async def admin_delete(request: Request):
    require_monitoring(request)
    body = await request.json()
    filename = (body or {}).get("filename", "").strip()

    # Path traversal protection
    if not filename or any(s in filename for s in ("/", "\\", "..")):
        return JSONResponse({"error": "Nom de fichier invalide"}, status_code=400)

    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return JSONResponse({"error": "Fichier introuvable"}, status_code=404)

    os.remove(path)
    track("reindex", detail=f"suppression : {filename}")
    logger.info(f"Fichier supprimé : {filename}")
    return {"message": f"'{filename}' supprimé. Réindexe pour mettre à jour Qdrant."}
