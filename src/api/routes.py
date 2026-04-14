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
from pydantic import BaseModel, Field

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
    get_conversation_owner, get_history, get_user_conversations, get_user_summary, save_exchange,
    save_user_summary, track,
)
from src.search.search import rechercher_passages
from src.security.validator import valider_entree

# ── Semantic cache ────────────────────────────────────────────────────────
from src.caching.semantic_cache import check as cache_check
from src.caching.semantic_cache import store as cache_store, stats as cache_stats

logger = logging.getLogger(__name__)

SUMMARY_UPDATE_INTERVAL = int(os.getenv("SUMMARY_UPDATE_INTERVAL", "5"))
IMPORTANCE_THRESHOLD    = int(os.getenv("SUMMARY_IMPORTANCE_MIN_LEN", "80"))
MAX_LOCK_CACHE_SIZE     = max(100, int(os.getenv("MAX_USER_LOCKS", "5000")))
BACKGROUND_WORKERS      = max(2, int(os.getenv("BACKGROUND_MAX_WORKERS", "8")))

_user_locks:  defaultdict = defaultdict(threading.Lock)
_locks_mutex              = threading.Lock()
_executor                 = concurrent.futures.ThreadPoolExecutor(max_workers=BACKGROUND_WORKERS)


def _get_user_lock(uid: str) -> threading.Lock:
    # WHY: Pruning evite une croissance mémoire non bornée en environnement multi-user.
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
    # WHY: Lock non-bloquant garantit qu'une seule tâche de résumé tourne par user.
    lock = _get_user_lock(uid)
    if not lock.acquire(blocking=False):
        return
    try:
        old_summary = get_user_summary(uid)
        new_summary = generer_resume_utilisateur(history, old_summary)
        if new_summary:
            try:
                from src.security.pii_masker import masquer
                new_summary = masquer(new_summary)
            except Exception:
                pass
            save_user_summary(uid, new_summary)
    except Exception as e:
        logger.warning(f"Background summary failed: {e}")
    finally:
        lock.release()


class AskBody(BaseModel):
    question: str = Field(..., max_length=5000)
    session_id: str = ""

class ReindexBody(BaseModel):
    force: bool = False

class FeedbackBody(BaseModel):
    session_id: str
    rating: int          # 1-5
    comment: str = ""


router = APIRouter()


@router.get("/health")
async def health_check():
    from src.ingestion.run import BM25_CORPUS_FILE
    from src.ingestion.vector_store import _get_client as get_qdrant
    from src.monitoring.tracker import _get_client as get_supabase

    checks = {
        "llm_key":      bool(os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")),
        "bm25_corpus":  os.path.exists(BM25_CORPUS_FILE),
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
        "supabase_url":      os.getenv("SUPABASE_URL", ""),
        "supabase_anon_key": os.getenv("SUPABASE_ANON_KEY", ""),
    }


@router.get("/api/auth/me")
async def get_user_identity(user_id: str = Depends(get_current_user)):
    return {"user_id": user_id}


@router.post("/api/ask")
@limiter.limit("1/5seconds;10/minute;100/day")
async def ask_oracle(request: Request, body: AskBody, user_id: str = Depends(get_current_user)):
    req_id  = str(uuid.uuid4())[:8]
    start   = time.time()
    question = body.question.strip()

    if not question:
        return JSONResponse({"error": "Question vide"}, status_code=400)

    if not user_id:
        return JSONResponse({"error": "Authentification requise."}, status_code=401)

    if body.session_id:
        owner = get_conversation_owner(body.session_id)
        if owner and owner != user_id:
            return JSONResponse({"error": "Accès refusé"}, status_code=403)

    # Masquage PII avant validation sécurité
    try:
        from src.security.pii_masker import masquer
        question = masquer(question)
    except Exception as e:
        logger.debug(f"PII masker ignoré : {e}")

    validation = valider_entree(question)
    if not validation["valid"]:
        bt = validation["type"]
        is_lakera = bt == "jailbreak"
        track("injection_lakera" if is_lakera else "injection_regex", detail=question[:200])
        msg = ("⚠️ L'Oracle a détecté une tentative de manipulation des arcanes sacrées."
               if bt in ("prompt_injection", "jailbreak") else
               "🔮 L'Oracle ne répond qu'aux questions sur le lore du jeu.")
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'meta', 'sources': [], 'confidence': 0})}\n\n",
                  f"data: {json.dumps({'type': 'text', 'text': msg})}\n\n",
                  f"data: {json.dumps({'type': 'done'})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Semantic cache check ──────────────────────────────────────────────
    cached = cache_check(question)
    if cached is not None:
        cached_text = cached[0] if isinstance(cached, tuple) else cached
        logger.info(f"[{req_id}] Cached response returned")
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'meta', 'sources': [], 'passages': [], 'confidence': 0})}\n\n",
                  f"data: {json.dumps({'type': 'text', 'text': cached_text})}\n\n",
                  f"data: {json.dumps({'type': 'done', 'model': 'cache'})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    history    = get_history(body.session_id)
    summary    = get_user_summary(user_id)
    memories   = search_user_memories(user_id, question)
    query      = reformuler_question(question, history)
    passages, sources, conf_scores = rechercher_passages(query)

    if not passages:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'meta', 'sources': [], 'confidence': 0})}\n\n",
                  f"data: {json.dumps({'type': 'text', 'text': 'Les archives ne contiennent aucune information sur ce sujet.'})}\n\n",
                  f"data: {json.dumps({'type': 'done'})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Score de confiance moyen (0–100 %)
    confidence_pct = round(sum(conf_scores) / len(conf_scores) * 100) if conf_scores else 0

    async def event_stream():
        accumulated, model_used = [], []
        try:
            yield f"data: {json.dumps({'type': 'meta', 'sources': sources, 'passages': passages, 'confidence': confidence_pct})}\n\n"

            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()   # WHY: get_event_loop() est deprecated Python 3.10+

            def produce():
                # WHY: stream_reponse est synchrone, la queue évite de bloquer la boucle événementielle.
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
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Une erreur interne est survenue.'})}\n\n"
                    return
                accumulated.append(data)
                yield f"data: {json.dumps({'type': 'text', 'text': data})}\n\n"

            model_name = model_used[0] if model_used else "unknown"
            yield f"data: {json.dumps({'type': 'done', 'model': model_name})}\n\n"

            if body.session_id:
                answer = "".join(accumulated)
                save_exchange(body.session_id, question, answer, user_id)
                cache_store(question, answer)
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
            yield f"data: {json.dumps({'type': 'error', 'message': 'Une erreur interne est survenue.'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/feedback")
async def submit_feedback(body: FeedbackBody, user_id: str = Depends(get_current_user)):
    """Cycle Human-in-the-Loop : stocke le feedback, déclenche le judge si rating ≤ 2."""
    if not (1 <= body.rating <= 5):
        return JSONResponse({"error": "rating doit être entre 1 et 5"}, status_code=400)

    def _persist_and_judge():
        from src.monitoring.tracker import _get_client
        judge_score = None

        if body.rating <= 2:
            try:
                from src.security.judge import evaluer_reponse
                # WHY: On récupère la dernière réponse de la conversation pour la juger.
                history = get_history(body.session_id)
                if history:
                    last = history[-1]
                    judge_score = evaluer_reponse(last["question"], last["answer"])
                    if judge_score is not None and judge_score < 0.5:
                        track("judge_flag", detail=f"session:{body.session_id} score:{judge_score:.2f}")
                        logger.warning(f"[JUDGE] Score faible ({judge_score:.2f}) pour session {body.session_id[:8]}")
            except Exception as e:
                logger.warning(f"[JUDGE] Évaluation échouée : {e}")

        client = _get_client()
        if not client:
            return
        try:
            client.table("feedback").insert({
                "session_id":  body.session_id,
                "user_id":     user_id,
                "rating":      body.rating,
                "comment":     body.comment[:500] if body.comment else "",
                "judge_score": judge_score,
            }).execute()
        except Exception as e:
            logger.warning(f"[FEEDBACK] Stockage échoué : {e}")

    _executor.submit(_persist_and_judge)
    return {"ok": True}


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
        return JSONResponse({"error": "Erreur interne lors de la réindexation."}, status_code=500)


@router.get("/api/conversations")
async def get_history_by_session(session_id: str = "", user_id: str = Depends(get_current_user)):
    if not session_id:
        return JSONResponse({"error": "session_id requis"}, status_code=400)
    if not conversation_belongs_to_user(session_id, user_id):
        return JSONResponse({"error": "Accès refusé"}, status_code=403)
    return {"exchanges": get_conversation(session_id)}


@router.get("/api/conversations/list")
async def list_user_conversations(user_id: str = Depends(get_current_user)):
    if not user_id:
        return JSONResponse({"error": "Authentification requise"}, status_code=401)
    return {"conversations": get_user_conversations(user_id)}


@router.get("/api/conversations/messages")
async def get_messages_for_session(session_id: str = "", user_id: str = Depends(get_current_user)):
    if not session_id:
        return JSONResponse({"error": "session_id requis"}, status_code=400)
    if not conversation_belongs_to_user(session_id, user_id):
        return JSONResponse({"error": "Accès refusé"}, status_code=403)
    client = None
    try:
        from src.monitoring.tracker import _get_client, _get_conv_id
        client = _get_client()
        if not client:
            return {"messages": []}
        cid = _get_conv_id(client, session_id)
        if not cid:
            return {"messages": []}
        r = (client.table("messages").select("id, role, content, created_at")
             .eq("conversation_id", cid)
             .order("id").execute())
        return {"messages": r.data or []}
    except Exception as e:
        logger.warning(f"get_messages_for_session: {e}")
        return {"messages": []}


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



@router.get("/api/cache/stats")
async def get_cache_stats(request: Request):
    """Return semantic cache metadata — accessible via monitoring key."""
    require_monitoring(request)
    return cache_stats()



@router.post("/api/ask_agent")
@limiter.limit("1/5seconds;10/minute;100/day")
async def ask_agent(request: Request, body: AskBody, user_id: str = Depends(get_current_user)):
    """ReAct agent endpoint — alternatif a /api/ask qui utilise un agent avec outils."""
    question = body.question.strip()
    if not question:
        return JSONResponse({"error": "Question vide"}, status_code=400)

    history = get_history(body.session_id) if body.session_id else []
    summary = get_user_summary(user_id) if user_id else ""
    memories = search_user_memories(user_id, question) if user_id else []

    # ReAct agent loop
    from src.agent.react_agent import run_react_agent
    result = run_react_agent(question)

    answer = result.get("answer", "")

    # Fallback to normal pipeline if agent returned raw passages
    if result.get("fallback") and len(answer.split("\n")) > 3:
        passages = [line for line in answer.split("\n") if line.strip()]
        answer_stream = stream_reponse(
            question, passages[:5], [], history,
            user_summary=summary, vector_memories=memories
        )
        full_answer = "".join(list(answer_stream))
        if full_answer:
            answer = full_answer

    # Save conversation
    if body.session_id and answer and answer != "No results found after agent search.":
        try:
            save_exchange(body.session_id, question, answer, user_id)
        except Exception:
            pass

    return JSONResponse({
        "reponse": answer,
        "tool_calls": result.get("tool_calls", []),
        "iterations": result.get("iterations", 0),
        "model_used": result.get("model", "unknown"),
        "sources": [],
    })


def register_routes(app: FastAPI, log_buffer: deque = None) -> None:
    # WHY: Attacher le buffer à l'app state évite les imports circulaires dans le monitoring.
    if log_buffer is not None:
        app.state.log_buffer = log_buffer
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(media_router)
    app.include_router(monitoring_router)
