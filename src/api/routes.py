import asyncio
import concurrent.futures
import json
import logging
import os
import threading
import time
import uuid
from collections import defaultdict, deque

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

SUMMARY_UPDATE_INTERVAL = int(os.getenv("SUMMARY_UPDATE_INTERVAL", "5"))
IMPORTANCE_THRESHOLD = int(os.getenv("SUMMARY_IMPORTANCE_MIN_LEN", "80"))
MAX_LOCK_CACHE_SIZE = max(100, int(os.getenv("MAX_USER_LOCKS", "5000")))
BACKGROUND_WORKERS = max(2, int(os.getenv("BACKGROUND_MAX_WORKERS", "8")))

_user_locks: defaultdict = defaultdict(threading.Lock)
_locks_mutex = threading.Lock()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=BACKGROUND_WORKERS)


def _get_user_lock(uid: str) -> threading.Lock:
    # WHY: Pruning the lock cache prevents unbounded memory growth in a multi-user environment.
    with _locks_mutex:
        if len(_user_locks) >= MAX_LOCK_CACHE_SIZE and uid not in _user_locks:
            removed = 0
            for key, lock in list(_user_locks.items()):
                if removed >= 50:
                    break
                if lock.acquire(blocking=False):
                    lock.release()
                    del _user_locks[key]
                    removed += 1
        return _user_locks[uid]


def _run_background_summary(uid: str, history: list) -> None:
    # WHY: Non-blocking lock ensures only one summary task runs per user at a time.
    lock = _get_user_lock(uid)
    if not lock.acquire(blocking=False):
        return
    try:
        old_summary = get_user_summary(uid)
        new_summary = generer_resume_utilisateur(history, old_summary)
        if new_summary:
            save_user_summary(uid, new_summary)
    except Exception as e:
        logger.warning(f"Background summary failed: {e}")
    finally:
        lock.release()


class AskBody(BaseModel):
    question: str
    session_id: str = ""

class ReindexBody(BaseModel):
    force: bool = False


router = APIRouter()


@router.get("/health")
async def health_check():
    from src.ingestion.run import BM25_CORPUS_FILE
    from src.ingestion.vector_store import _get_client as get_qdrant
    from src.monitoring.tracker import _get_client as get_supabase

    checks = {
        "llm_key": bool(os.getenv("OPENAI_API_KEY")),
        "bm25_corpus": os.path.exists(BM25_CORPUS_FILE),
        "vector_memory": os.getenv("VECTOR_MEMORY_ENABLED", "false").lower() != "false",
    }
    try:
        get_qdrant().get_collections()
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False
    try:
        supabase = get_supabase()
        if supabase:
            supabase.table("events").select("id").limit(1).execute()
            checks["supabase"] = True
        else:
            checks["supabase"] = False
    except Exception:
        checks["supabase"] = False

    is_healthy = all(v for k, v in checks.items() if k != "vector_memory")
    return JSONResponse(
        {"status": "ok" if is_healthy else "degraded", "checks": checks},
        status_code=200 if is_healthy else 207,
    )


@router.get("/api/auth/config")
async def get_auth_config():
    return {
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    }


@router.get("/api/auth/me")
async def get_user_identity(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}


@router.post("/api/ask")
@limiter.limit("1/5seconds;10/minute;100/day")
async def ask_oracle(request: Request, body: AskBody, user_id: str = Depends(get_current_user)):
    req_id = str(uuid.uuid4())[:8]
    start = time.time()
    question = body.question.strip()

    if not question:
        return JSONResponse({"error": "Question vide"}, status_code=400)

    if body.session_id:
        owner = get_conversation_owner(body.session_id)
        if owner and owner != user_id:
            return JSONResponse({"error": "Accès refusé"}, status_code=403)

    validation = valider_entree(question)
    if not validation["valid"]:
        bt = validation["type"]
        is_threat = bt == "jailbreak" or "Lakera" in validation.get("reason", "")
        track("injection_lakera" if is_threat else "injection_regex", detail=question[:200])
        msg = ("⚠️ L'Oracle a détecté une tentative de manipulation des arcanes sacrées."
               if bt in ("prompt_injection", "jailbreak") else
               "🔮 L'Oracle ne répond qu'aux questions sur le lore du jeu.")
        return JSONResponse({"reponse": msg, "blocked": True, "block_type": bt, "sources": [], "passages": []})

    history = get_history(body.session_id)
    summary = get_user_summary(user_id)
    memories = search_user_memories(user_id, question)
    query = reformuler_question(question, history)
    passages, sources = rechercher_passages(query)

    if not passages:
        return JSONResponse({"reponse": "Les archives ne contiennent aucune information sur ce sujet.", "sources": [], "passages": []})

    async def event_stream():
        accumulated, model_used = [], []
        try:
            yield f"data: {json.dumps({'type': 'meta', 'sources': sources, 'passages': passages})}\n\n"

            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def produce():
                # WHY: stream_reponse is sync and must be bridged via a queue to avoid blocking the event loop.
                try:
                    for chunk in stream_reponse(question, passages, sources, history,
                                                model_used=model_used, user_summary=summary,
                                                vector_memories=memories):
                        loop.call_soon_threadsafe(queue.put_nowait, ("text", chunk))
                except Exception as e:
                    loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

            _executor.submit(produce)

            while True:
                kind, data = await queue.get()
                if kind == "done":
                    break
                if kind == "error":
                    track("error", detail=data[:200])
                    yield f"data: {json.dumps({'type': 'error', 'message': data})}\n\n"
                    return
                accumulated.append(data)
                yield f"data: {json.dumps({'type': 'text', 'text': data})}\n\n"

            model_name = model_used[0] if model_used else "unknown"
            yield f"data: {json.dumps({'type': 'done', 'model': model_name})}\n\n"

            if body.session_id:
                answer = "".join(accumulated)
                save_exchange(body.session_id, question, answer, user_id)
                if len(question) + len(answer) > IMPORTANCE_THRESHOLD:
                    count = count_user_exchanges(user_id)
                    if count > 0 and count % SUMMARY_UPDATE_INTERVAL == 0:
                        _executor.submit(_run_background_summary, user_id, history)
                    _executor.submit(add_user_memory, user_id, question, answer)

            latency = int((time.time() - start) * 1000)
            track("question", detail=f"{question[:150]} | model:{model_name}", latency_ms=latency)
            logger.info(f"[{req_id}] {model_name} ({latency}ms)")

        except Exception as e:
            track("error", detail=str(e)[:200])
            logger.error(f"[{req_id}] Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/reindex")
@limiter.limit("5/hour")
async def trigger_reindex(request: Request, body: ReindexBody):
    require_monitoring(request)
    try:
        result = index_data(force_reindex=body.force)
        track("reindex", detail=f"force={body.force} | {'changed' if result else 'none'}")
        return {"message": "Indexation terminée." if result else "Déjà à jour."}
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/conversations")
async def get_history_by_session(session_id: str = "", user_id: str = Depends(get_current_user)):
    if not session_id:
        return JSONResponse({"error": "session_id requis"}, status_code=400)
    if not conversation_belongs_to_user(session_id, user_id):
        return JSONResponse({"error": "Accès refusé"}, status_code=403)
    return {"exchanges": get_conversation(session_id)}


@router.delete("/api/conversations")
async def delete_history_by_session(session_id: str = "", user_id: str = Depends(get_current_user)):
    if not session_id:
        return JSONResponse({"error": "session_id requis"}, status_code=400)
    if not conversation_belongs_to_user(session_id, user_id):
        return JSONResponse({"error": "Accès refusé"}, status_code=403)
    delete_conversation(session_id)
    return {"ok": True}


@router.get("/api/monitoring/logs")
async def get_system_logs(request: Request):
    require_monitoring(request)
    logs = getattr(request.app.state, "log_buffer", None)
    return {"logs": list(logs or [])}


def register_routes(app: FastAPI, log_buffer: deque = None) -> None:
    # WHY: Attaching the log buffer to app state allows the monitoring endpoint to access it without circular imports.
    if log_buffer is not None:
        app.state.log_buffer = log_buffer
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(media_router)
    app.include_router(monitoring_router)
