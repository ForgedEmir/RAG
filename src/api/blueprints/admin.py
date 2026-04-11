import logging
import os
import re
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import JSONResponse
from src.api.auth import require_monitoring
from src.api.limiter import limiter
from src.ingestion.run import index_data
from src.monitoring.tracker import track
from src.security.validator import valider_entree

logger = logging.getLogger(__name__)
admin_router = APIRouter()

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_KB", "500")) * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".xlsx", ".pdf"}
DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample"))
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._ -]{1,120}$")


def _sanitize_filename(raw_name: str) -> str:
    """Return a safe basename or an empty string when invalid."""
    name = os.path.basename((raw_name or "").replace("\x00", "")).strip()
    if not name or name in {".", ".."}:
        return ""
    if any(sep in name for sep in ("/", "\\")):
        return ""
    if ".." in name:
        return ""
    if not _SAFE_FILENAME_RE.match(name):
        return ""
    return name


def _count_points_for_filename(filename: str) -> int | None:
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        from src.ingestion.vector_store import get_store
        store = get_store(force_reindex=False)
        result = store.client.count(
            collection_name="lore",
            count_filter=Filter(
                should=[FieldCondition(key="metadata.fichier", match=MatchValue(value=filename))]
            ),
            exact=True,
        )
        return int(getattr(result, "count", 0))
    except Exception as e:
        logger.warning(f"Vérification Qdrant impossible pour '{filename}': {e}")
        return None


@admin_router.get("/api/admin/sources")
async def admin_sources(request: Request):
    require_monitoring(request)
    from src.ingestion.run import list_current_files
    files = list_current_files()
    return {"files": sorted(files.keys()), "total": len(files)}


@admin_router.post("/api/admin/upload")
@limiter.limit("20/hour")
async def admin_upload(request: Request, file: UploadFile = File(...)):
    require_monitoring(request)

    safe_name = _sanitize_filename(file.filename or "")
    if not safe_name:
        return JSONResponse({"error": "Nom de fichier invalide."}, status_code=400)

    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": f"Extension non supportée. Formats : {', '.join(ALLOWED_EXTENSIONS)}"}, status_code=400)

    content = await file.read()
    if not content:
        return JSONResponse({"error": "Fichier vide."}, status_code=400)
    if len(content) > MAX_UPLOAD_SIZE:
        size_kb, limit_kb = len(content) // 1024, MAX_UPLOAD_SIZE // 1024
        return JSONResponse({"error": f"Fichier trop volumineux ({size_kb} Ko). Max : {limit_kb} Ko."}, status_code=400)

    try:
        text = content.decode("utf-8", errors="ignore") if ext in {".txt", ".md", ".csv", ".json", ".xml"} else ""
    except Exception:
        return JSONResponse({"error": "Encodage invalide."}, status_code=400)

    # Security check on a representative sample to avoid high latency on large files
    lines = text.splitlines()
    if len(lines) > 50:
        mid = len(lines) // 2
        sample = "\n".join(lines[:20] + lines[max(0, mid - 5):mid + 5] + lines[-20:])
    else:
        sample = text

    # Binary formats: shallow marker for validator path, keep low latency.
    if not sample and ext in {".pdf", ".xlsx"}:
        sample = f"BINARY_FILE:{ext}:{safe_name}:{len(content)}"

    validation = valider_entree(sample)
    if not validation["valid"]:
        logger.warning(f"Upload blocked [{validation['type']}] — '{safe_name}'")
        track("upload_blocked", detail=f"{safe_name} | {validation['type']}")
        return JSONResponse({"error": "Contenu suspect. Upload refusé."}, status_code=400)

    os.makedirs(DATA_DIR, exist_ok=True)
    destination = os.path.join(DATA_DIR, safe_name)
    existed_before = os.path.exists(destination)

    with open(destination, "wb") as out:
        out.write(content)

    reindex_warning = None
    changed = None
    try:
        changed = bool(index_data(force_reindex=False))
    except Exception as e:
        reindex_warning = str(e)
        logger.warning(f"Upload réindexation automatique échouée: {e}")

    qdrant_points = _count_points_for_filename(safe_name)

    if existed_before:
        track("replace", detail=f"{safe_name} | {len(content)//1024} Ko (upsert)")
        logger.info(f"Fichier remplacé (upsert upload) : {safe_name}")
        payload = {"message": f"'{safe_name}' remplacé et indexé.", "filename": safe_name}
    else:
        track("upload", detail=f"{safe_name} | {len(content)//1024} Ko")
        logger.info(f"Fichier uploadé : {safe_name}")
        payload = {"message": f"'{safe_name}' uploadé et indexé.", "filename": safe_name}

    payload["ingestion"] = {
        "changed": changed,
        "qdrant_points": qdrant_points,
        "verified": (qdrant_points is not None and qdrant_points > 0),
        "summary": (
            f"Ingestion {'mise à jour' if changed else 'sans changement détecté'}; "
            + (f"Qdrant={qdrant_points} chunk(s)." if qdrant_points is not None else "Qdrant non vérifiable.")
        ),
    }
    if reindex_warning:
        payload["warning"] = "Fichier uploadé, mais la réindexation automatique a échoué."
    return payload


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

    # Suppression immédiate des chunks Qdrant liés au fichier pour garantir la cohérence.
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        from src.ingestion.vector_store import get_store, remove_files
        store = get_store(force_reindex=False)
        remove_files(store, {filename})
    except Exception as e:
        logger.warning(f"Delete Qdrant immédiat échoué: {e}")

    reindex_warning = None
    changed = None
    try:
        changed = bool(index_data(force_reindex=False))
    except Exception as e:
        reindex_warning = str(e)
        logger.warning(f"Delete réindexation automatique échouée: {e}")

    qdrant_points = _count_points_for_filename(filename)

    track("reindex", detail=f"suppression : {filename}")
    logger.info(f"Fichier supprimé : {filename}")
    payload = {"message": f"'{filename}' supprimé et index mis à jour."}
    payload["ingestion"] = {
        "changed": changed,
        "qdrant_points": qdrant_points,
        "verified": (qdrant_points == 0) if qdrant_points is not None else False,
        "summary": (
            f"Ingestion {'mise à jour' if changed else 'sans changement détecté'}; "
            + (f"Qdrant={qdrant_points} chunk(s) restant(s)." if qdrant_points is not None else "Qdrant non vérifiable.")
        ),
    }
    if reindex_warning:
        payload["warning"] = "Fichier supprimé, mais la réindexation automatique a échoué."
    return payload
