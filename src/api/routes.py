"""Routes FastAPI — core (/api/ask, /api/reindex, /api/conversations, /health, /api/monitoring/logs)."""
import asyncio
import concurrent.futures
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.api.auth import get_current_user, require_monitoring
from src.api.limiter import limiter
from src.api.blueprints.admin import admin_router
from src.api.blueprints.media import media_router
from src.api.blueprints.monitoring_bp import monitoring_router
from src.generation.generator import generer_resume_utilisateur, reformuler_question, stream_reponse
from src.ingestion.run import index_data
from src.memory.vector_memory import add_user_memory, search_user_memories
from src.monitoring.tracker import (
    conversation_belongs_to_user, count_user_exchanges, delete_conversation, get_conversation,
    get_conversation_owner, get_history, get_user_summary, save_exchange, save_user_summary, track,
)
from src.search.search import rechercher_passages
from src.security.validator import valider_entree

logger = logging.getLogger(__name__)

_SUMMARY_INTERVAL   = int(os.getenv("SUMMARY_UPDATE_INTERVAL", "5"))
_IMPORTANCE_MIN_LEN = int(os.getenv("SUMMARY_IMPORTANCE_MIN_LEN", "80"))
_user_locks: dict   = defaultdict(threading.Lock)
_user_locks_mutex   = threading.Lock()
_MAX_USER_LOCKS     = max(100, int(os.getenv("MAX_USER_LOCKS", "5000")))
_bg_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(2, int(os.getenv("BACKGROUND_MAX_WORKERS", "8")))
)


def _get_user_lock(uid: str) -> threading.Lock:
    with _user_locks_mutex:
        if len(_user_locks) >= _MAX_USER_LOCKS and uid not in _user_locks:
            # Évite une croissance infinie: retire quelques verrous inactifs.
            removed = 0
            for key, lock in list(_user_locks.items()):
                if removed >= 50:
                    break
                if lock.acquire(blocking=False):
                    lock.release()
                    del _user_locks[key]
                    removed += 1
        return _user_locks[uid]


def _is_important(q: str, a: str) -> bool:
    return len(q) + len(a) > _IMPORTANCE_MIN_LEN


def _run_summary(uid: str, history: list) -> None:
    lock = _get_user_lock(uid)
    if not lock.acquire(blocking=False):
        return
    try:
        old = get_user_summary(uid)
        new = generer_resume_utilisateur(history, old)
        if new:
            save_user_summary(uid, new)
    except Exception as e:
        logger.warning(f"Résumé background : {e}")
    finally:
        lock.release()


# ── Modèles Pydantic ──────────────────────────────────────────────────────────

class AskBody(BaseModel):
    question: str
    session_id: str = ""
    user_id: Optional[str] = None  # legacy, ignoré quand l'auth JWT est active


class ReindexBody(BaseModel):
    force: bool = False


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter()


@router.get("/health")
async def health():
    checks: dict = {}
    checks["llm_key"] = bool(os.getenv("OPENAI_API_KEY"))

    from src.ingestion.run import BM25_CORPUS_FILE
    checks["bm25_corpus"] = os.path.exists(BM25_CORPUS_FILE)

    try:
        from src.ingestion.vector_store import _get_client
        _get_client().get_collections()
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False

    try:
        from src.monitoring.tracker import _get_client as _supa
        supa = _supa()
        if supa:
            supa.table("events").select("id").limit(1).execute()
            checks["supabase"] = True
        else:
            checks["supabase"] = False
    except Exception:
        checks["supabase"] = False

    checks["vector_memory"] = os.getenv("VECTOR_MEMORY_ENABLED", "false").lower() != "false"

    ok = all(v for k, v in checks.items() if k != "vector_memory")
    return JSONResponse({"status": "ok" if ok else "degraded", "checks": checks},
                        status_code=200 if ok else 207)


@router.get("/api/auth/config")
async def auth_config():
    return {
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    }


@router.get("/api/auth/me")
async def auth_me(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}


@router.post("/api/ask")
@limiter.limit("1/5seconds;10/minute;100/day")
async def ask(request: Request, body: AskBody, user_id: str = Depends(get_current_user)):
    req_id = str(uuid.uuid4())[:8]
    start  = time.time()

    user_id = user_id or ""
    question   = body.question.strip()
    session_id = body.session_id

    if not question:
        return JSONResponse({"error": "Question vide"}, status_code=400)
    if not user_id:
        return JSONResponse({"error": "Authentification requise"}, status_code=401)

    owner = get_conversation_owner(session_id) if session_id else ""
    if owner and owner != user_id:
        return JSONResponse({"error": "Accès refusé à cette session"}, status_code=403)

    validation = valider_entree(question)
    if not validation["valid"]:
        bt = validation["type"]
        is_lakera = "Lakera" in validation.get("reason", "")
        track("injection_lakera" if (is_lakera or bt == "jailbreak") else "injection_regex",
              detail=question[:200])
        msg = (
            "⚠️ L'Oracle a détecté une tentative de manipulation des arcanes sacrées."
            if bt in ("prompt_injection", "jailbreak") else
            "🔮 L'Oracle ne répond qu'aux questions sur le lore du jeu."
        )
        return JSONResponse({"reponse": msg, "sources": [], "passages": [],
                             "blocked": True, "block_type": bt})

    history         = get_history(session_id)
    user_summary    = get_user_summary(user_id)
    vector_memories = search_user_memories(user_id, question)
    query           = reformuler_question(question, history)
    passages, sources = rechercher_passages(query)

    if not passages:
        return JSONResponse({"reponse": "Les archives ne contiennent aucune information sur ce sujet.",
                             "sources": [], "passages": [], "blocked": False})

    async def event_stream():
        accumulated: list = []
        model_used:  list = []
        try:
            yield f"data: {json.dumps({'type': 'meta', 'sources': sources, 'passages': passages})}\n\n"

            # stream_reponse est synchrone — on l'exécute dans un thread
            q: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def produce():
                try:
                    for chunk in stream_reponse(
                        question, passages, sources, history,
                        model_used=model_used, user_summary=user_summary,
                        vector_memories=vector_memories,
                    ):
                        loop.call_soon_threadsafe(q.put_nowait, ("text", chunk))
                except Exception as e:
                    loop.call_soon_threadsafe(q.put_nowait, ("error", str(e)))
                finally:
                    loop.call_soon_threadsafe(q.put_nowait, ("done", None))

            _bg_executor.submit(produce)

            while True:
                kind, data = await q.get()
                if kind == "done":
                    break
                elif kind == "error":
                    track("error", detail=data[:200])
                    yield f"data: {json.dumps({'type': 'error', 'message': data})}\n\n"
                    return
                else:
                    accumulated.append(data)
                    yield f"data: {json.dumps({'type': 'text', 'text': data})}\n\n"

            model_name = model_used[0] if model_used else "inconnu"
            yield f"data: {json.dumps({'type': 'done', 'model': model_name})}\n\n"

            # Post-traitement en background
            if session_id:
                answer = "".join(accumulated)
                save_exchange(session_id, question, answer, user_id)
                if _is_important(question, answer):
                    total = count_user_exchanges(user_id)
                    if total > 0 and total % _SUMMARY_INTERVAL == 0:
                        _bg_executor.submit(_run_summary, user_id, history)
                    _bg_executor.submit(add_user_memory, user_id, question, answer)

            latency = int((time.time() - start) * 1000)
            track("question", detail=f"{question[:150]} | model:{model_name}", latency_ms=latency)
            logger.info(f"[{req_id}] {model_name} ({latency}ms)")

        except Exception as e:
            track("error", detail=str(e)[:200])
            logger.error(f"[{req_id}] Erreur stream : {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/reindex")
@limiter.limit("5/hour")
async def reindex(request: Request, body: ReindexBody):
    require_monitoring(request)
    try:
        result = index_data(force_reindex=body.force)
        msg = "Indexation terminée." if result else "Déjà à jour."
        track("reindex", detail=f"force={body.force} | {'changements' if result else 'aucun'}")
        return {"message": msg}
    except Exception as e:
        logger.error(f"Reindex : {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/conversations")
async def get_conv(session_id: str = "", user_id: str = Depends(get_current_user)):
    if not session_id:
        return JSONResponse({"error": "session_id requis"}, status_code=400)
    if not conversation_belongs_to_user(session_id, user_id):
        return JSONResponse({"error": "Accès refusé"}, status_code=403)
    return {"exchanges": get_conversation(session_id)}


@router.delete("/api/conversations")
async def del_conv(session_id: str = "", user_id: str = Depends(get_current_user)):
    if not session_id:
        return JSONResponse({"error": "session_id requis"}, status_code=400)
    if not conversation_belongs_to_user(session_id, user_id):
        return JSONResponse({"error": "Accès refusé"}, status_code=403)
    delete_conversation(session_id)
    return {"ok": True}


@router.get("/api/monitoring/logs")
async def monitoring_logs(request: Request):
    require_monitoring(request)
    buf = getattr(request.app.state, "log_buffer", None)
    return {"logs": list(buf or [])}


# ── Enregistrement ────────────────────────────────────────────────────────────

def register_routes(app: FastAPI, log_buffer: deque = None) -> None:
    if log_buffer is not None:
        app.state.log_buffer = log_buffer
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(media_router)
    app.include_router(monitoring_router)
