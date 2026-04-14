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

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_KB", "500")) * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".xlsx"}
DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample"))

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

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": f"Extension non supportée. Formats : {', '.join(ALLOWED_EXTENSIONS)}"}, status_code=400)

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        size_kb, limit_kb = len(content) // 1024, MAX_UPLOAD_SIZE // 1024
        return JSONResponse({"error": f"Fichier trop volumineux ({size_kb} Ko). Max : {limit_kb} Ko."}, status_code=400)

    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        return JSONResponse({"error": "Encodage invalide."}, status_code=400)

    # Security check on a representative sample to avoid high latency on large files
    lines = text.splitlines()
    if len(lines) > 50:
        mid = len(lines) // 2
        sample = "\n".join(lines[:20] + lines[max(0, mid-5):mid+5] + lines[-20:])
    else:
        sample = text

    validation = valider_entree(sample)
    if not validation["valid"]:
        logger.warning(f"Upload blocked [{validation['type']}] — '{file.filename}'")
        track("upload_blocked", detail=f"{file.filename} | {validation['type']}")
        return JSONResponse({"error": "Contenu suspect. Upload refusé."}, status_code=400)

    os.makedirs(DATA_DIR, exist_ok=True)
    destination = os.path.join(DATA_DIR, os.path.basename(file.filename or "upload"))
    with open(destination, "wb") as out:
        out.write(content)

    track("upload", detail=f"{file.filename} | {len(content)//1024} Ko")
    logger.info(f"Fichier uploadé : {file.filename}")
    return {"message": f"'{file.filename}' uploadé. Réindexe pour l'activer.", "filename": file.filename}

@admin_router.post("/api/evaluate")
@limiter.limit("30/hour")
async def evaluate_rag_endpoint(request: Request):
    """Evaluate RAG quality for a given question / contexts / answer triple.

    Body (JSON):
        question  : str
        contexts  : list[str]   — retrieved passages used to generate the answer
        answer    : str

    Returns RAGAS scores: faithfulness, answer_relevancy, context_precision (0–1).
    """
    require_monitoring(request)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Corps JSON invalide."}, status_code=400)

    question = (body or {}).get("question", "").strip()
    contexts = (body or {}).get("contexts", [])
    answer = (body or {}).get("answer", "").strip()

    if not question or not answer:
        return JSONResponse({"error": "Les champs 'question' et 'answer' sont requis."}, status_code=400)
    if not isinstance(contexts, list):
        return JSONResponse({"error": "'contexts' doit être une liste de chaînes."}, status_code=400)

    from src.evaluation.ragas_eval import evaluate_rag
    scores = evaluate_rag(question, [str(c) for c in contexts], answer)
    track("evaluate", detail=f"q={question[:60]}")
    return {"scores": scores}


@admin_router.delete("/api/admin/delete")
async def admin_delete(request: Request):
    require_monitoring(request)
    body = await request.json()
    raw_filename = (body or {}).get("filename", "").strip()

    # Normalise pour éliminer tout composant de chemin
    filename = os.path.basename(raw_filename)

    # Rejette si vide, si le nom a changé après basename (chemin traversal), ou si des
    # caractères suspects subsistent
    if not filename or filename != raw_filename or any(s in filename for s in ("\x00",)):
        return JSONResponse({"error": "Nom de fichier invalide"}, status_code=400)

    # Vérification supplémentaire : le chemin résolu doit rester dans DATA_DIR
    path = os.path.realpath(os.path.join(DATA_DIR, filename))
    if not path.startswith(os.path.realpath(DATA_DIR) + os.sep):
        return JSONResponse({"error": "Nom de fichier invalide"}, status_code=400)

    if not os.path.exists(path):
        return JSONResponse({"error": "Fichier introuvable"}, status_code=404)

    os.remove(path)
    track("reindex", detail=f"suppression : {filename}")
    logger.info(f"Fichier supprimé : {filename}")
    return {"message": f"'{filename}' supprimé. Réindexe pour mettre à jour Qdrant."}
