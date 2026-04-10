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
    get_conversation_owner, get_history, get_trace_context, get_user_conversations,
    get_user_summary, record_feedback_event, register_trace_context, save_exchange,
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
MAX_RESPONSE_SECONDS    = float(os.getenv("MAX_RESPONSE_SECONDS", "0"))

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


def _is_uuid(value: str) -> bool:
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except Exception:
        return False


def _resolve_feedback_context(session_id: str = "", question: str = "", answer: str = "") -> tuple[str, str]:
    q = (question or "").strip()
    a = (answer or "").strip()
    if (q and a) or not session_id:
        return q, a

    history = get_history(session_id)
    if not history:
        return q, a

    last = history[-1]
    return q or (last.get("question") or ""), a or (last.get("answer") or "")



class AskBody(BaseModel):
    question: str
    session_id: str = ""

class ReindexBody(BaseModel):
    force: bool = False

class FeedbackBody(BaseModel):
    session_id: str
    rating: int          # 1-5
    comment: str = ""


class FeedbackVoteBody(BaseModel):
    trace_id: str
    value: int           # -1 or +1
    session_id: str = ""
    question: str = ""
    answer: str = ""
    comment: str = ""


router = APIRouter()


@router.get("/health")
async def health_check():
    from src.ingestion.run import BM25_CORPUS_FILE
    from src.ingestion.vector_store import _get_client as get_qdrant
    from src.monitoring.tracker import _get_client as get_supabase

    checks = {
        "llm_key":      bool(os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")),
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
@limiter.limit("2/5seconds;30/minute;500/day")
async def ask_oracle(request: Request, body: AskBody, user_id: str = Depends(get_current_user)):
    trace_id = str(uuid.uuid4())
    req_id  = trace_id[:8]
    start   = time.time()
    question = body.question.strip()

    if not question:
        return JSONResponse({"error": "Question vide"}, status_code=400)

    if not user_id:
        return JSONResponse({"error": "Authentification requise."}, status_code=401)

    if body.session_id:
        owner = get_conversation_owner(body.session_id)
        from src.monitoring.tracker import _normalize_user_id as _norm_uid
        if owner and owner != _norm_uid(user_id):
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
                  f"data: {json.dumps({'type': 'done', 'trace_id': trace_id, 'question_for_feedback': question})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Détection questions méta (sur l'Oracle lui-même) ─────────────────
    _META_KEYWORDS = (
        "user-memory", "user memory", "mémoire utilisateur", "ta mémoire",
        "mes données", "mon profil", "tu sais quoi sur moi", "qu'est-ce que tu sais",
        "qui es-tu", "qui es tu", "tu es qui", "comment tu fonctionnes",
        "comment fonctionne", "ton fonctionnement", "tes données", "ta base de données",
        "tu stockes", "tu enregistres", "qu'est-ce que tu es",
    )
    q_lower = question.lower()
    if any(kw in q_lower for kw in _META_KEYWORDS):
        meta_msg = "🔮 Je suis l'Oracle des Archives, gardien du lore d'Aethelgard Online. Je réponds uniquement aux questions sur l'univers du jeu — son histoire, ses personnages, ses factions et ses événements. Pour toute question technique sur le service, contacte les développeurs."
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'meta', 'sources': [], 'confidence': 0})}\n\n",
                  f"data: {json.dumps({'type': 'text', 'text': meta_msg})}\n\n",
                  f"data: {json.dumps({'type': 'done', 'trace_id': trace_id, 'question_for_feedback': question})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Semantic cache check ──────────────────────────────────────────────
    cached = cache_check(question)
    if cached is not None:
        cached_text = cached[0] if isinstance(cached, tuple) else cached
        register_trace_context(trace_id, question, cached_text, body.session_id, user_id)
        logger.info(f"[{req_id}] Cached response returned")
        if body.session_id:
            _executor.submit(save_exchange, body.session_id, question, cached_text, user_id)
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'meta', 'sources': [], 'passages': [], 'confidence': 0})}\n\n",
                  f"data: {json.dumps({'type': 'text', 'text': cached_text})}\n\n",
                  f"data: {json.dumps({'type': 'done', 'model': 'cache', 'trace_id': trace_id, 'question_for_feedback': question})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Les 3 appels sont indépendants; exécution parallèle sur l'executor partagé.
    loop = asyncio.get_running_loop()
    history_f = loop.run_in_executor(_executor, get_history, body.session_id)
    summary_f = loop.run_in_executor(_executor, get_user_summary, user_id)
    memories_f = loop.run_in_executor(_executor, search_user_memories, user_id, question)
    history, summary, memories = await asyncio.gather(history_f, summary_f, memories_f, return_exceptions=True)
    if isinstance(history, Exception):
        logger.warning(f"[{req_id}] history fetch failed: {history}")
        history = []
    if isinstance(summary, Exception):
        logger.warning(f"[{req_id}] summary fetch failed: {summary}")
        summary = ""
    if isinstance(memories, Exception):
        logger.warning(f"[{req_id}] memory fetch failed: {memories}")
        memories = []

    t_ref = time.time()
    query = await asyncio.to_thread(reformuler_question, question, history)
    logger.info(f"[{req_id}] reformulation={int((time.time()-t_ref)*1000)}ms")

    t_search = time.time()
    passages, sources, conf_scores = await asyncio.to_thread(rechercher_passages, query)
    logger.info(f"[{req_id}] search={int((time.time()-t_search)*1000)}ms passages={len(passages)}")

    if not passages:
        no_data_msg = "Les archives ne contiennent aucune information sur ce sujet."
        register_trace_context(trace_id, question, no_data_msg, body.session_id, user_id)
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'meta', 'sources': [], 'confidence': 0})}\n\n",
                  f"data: {json.dumps({'type': 'text', 'text': no_data_msg})}\n\n",
                  f"data: {json.dumps({'type': 'done', 'trace_id': trace_id, 'question_for_feedback': question})}\n\n"]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Score de confiance moyen (0–100 %)
    confidence_pct = round(sum(conf_scores) / len(conf_scores) * 100) if conf_scores else 0

    async def event_stream():
        accumulated, model_used = [], []
        timed_out = False
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
                if MAX_RESPONSE_SECONDS > 0:
                    remaining = MAX_RESPONSE_SECONDS - (time.time() - start)
                    if remaining <= 0:
                        timed_out = True
                        logger.warning(f"[{req_id}] response timeout after {MAX_RESPONSE_SECONDS}s")
                        break
                    try:
                        kind, data = await asyncio.wait_for(queue.get(), timeout=remaining)
                    except asyncio.TimeoutError:
                        timed_out = True
                        logger.warning(f"[{req_id}] response timeout after {MAX_RESPONSE_SECONDS}s")
                        break
                else:
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
            if timed_out:
                yield f"data: {json.dumps({'type': 'text', 'text': ' [Reponse interrompue pour respecter la latence cible.]'})}\n\n"
                model_name = f"{model_name} [timeout]"

            answer = "".join(accumulated)
            register_trace_context(trace_id, question, answer, body.session_id, user_id)
            yield f"data: {json.dumps({'type': 'done', 'model': model_name, 'trace_id': trace_id, 'question_for_feedback': question})}\n\n"

            if body.session_id:
                save_exchange(body.session_id, question, answer, user_id)
                cache_store(question, answer)
                if len(question) + len(answer) > IMPORTANCE_THRESHOLD:
                    # WHY: count_user_exchanges is a Supabase round-trip — run it in the
                    # thread pool so it never blocks the SSE stream post-response.
                    def _maybe_summary(uid=user_id, hist=history):
                        count = count_user_exchanges(uid)
                        if count > 0 and count % SUMMARY_UPDATE_INTERVAL == 0:
                            _run_background_summary(uid, hist)
                    _executor.submit(_maybe_summary)
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


@router.post("/api/feedback")
async def submit_feedback(body: FeedbackBody, user_id: str = Depends(get_current_user)):
    """Cycle Human-in-the-Loop : stocke le feedback, déclenche le judge si rating ≤ 2."""
    if not (1 <= body.rating <= 5):
        return JSONResponse({"error": "rating doit être entre 1 et 5"}, status_code=400)

    def _persist_and_judge():
        from src.monitoring.tracker import _get_client
        question, answer = "", ""
        if body.rating <= 2:
            question, answer = _resolve_feedback_context(body.session_id)

        client = _get_client()
        if client and _is_uuid(body.session_id):
            try:
                client.table("feedback").insert({
                    "session_id": body.session_id,
                    "user_id":    user_id,
                    "rating":     body.rating,
                    "comment":    body.comment[:500] if body.comment else "",
                }).execute()
            except Exception as e:
                logger.warning(f"[FEEDBACK] Storage failed: {e}")

        value = 1 if body.rating >= 4 else (-1 if body.rating <= 2 else 0)
        record_feedback_event(
            value=value,
            rating=body.rating,
            user_id=user_id,
            source="legacy",
            session_id=body.session_id,
            question=question,
            answer=answer,
            comment=body.comment,
        )
        track("feedback_legacy", detail=f"rating:{body.rating} session:{body.session_id[:8]}")

    _executor.submit(_persist_and_judge)
    return {"ok": True}


@router.post("/api/feedback/vote")
async def submit_feedback_vote(body: FeedbackVoteBody, user_id: str = Depends(get_current_user)):
    trace_id = (body.trace_id or "").strip()
    if not trace_id:
        return JSONResponse({"error": "trace_id requis"}, status_code=400)
    if body.value not in (-1, 1):
        return JSONResponse({"error": "value doit etre -1 ou 1"}, status_code=400)

    context = get_trace_context(trace_id)
    trace_owner = (context.get("user_id") or "").strip()
    from src.monitoring.tracker import _normalize_user_id as _norm_uid
    if trace_owner and trace_owner != _norm_uid(user_id):
        return JSONResponse({"error": "Acces refuse"}, status_code=403)

    session_id = (body.session_id or context.get("session_id") or "").strip()
    if session_id:
        owner = get_conversation_owner(session_id)
        if owner and owner != _norm_uid(user_id):
            return JSONResponse({"error": "Acces refuse"}, status_code=403)

    question, answer = _resolve_feedback_context(
        session_id,
        question=body.question or context.get("question", ""),
        answer=body.answer or context.get("answer", ""),
    )
    rating = 5 if body.value > 0 else 1

    def _persist_vote():
        from src.monitoring.tracker import _get_client

        client = _get_client()
        safe_comment = body.comment[:500] if body.comment else ""
        db_comment = (f"[trace:{trace_id[:16]}] {safe_comment}").strip()
        if client and _is_uuid(session_id):
            try:
                client.table("feedback").insert({
                    "session_id": session_id,
                    "user_id":    user_id,
                    "rating":     rating,
                    "comment":    db_comment,
                }).execute()
            except Exception as e:
                logger.warning(f"[FEEDBACK] Vote storage failed: {e}")

        record_feedback_event(
            value=body.value,
            rating=rating,
            user_id=user_id,
            source="vote",
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            answer=answer,
            comment=body.comment,
        )
        track("feedback_vote", detail=f"value:{body.value} trace:{trace_id[:8]} session:{session_id[:8]}")

    _executor.submit(_persist_vote)
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
        return JSONResponse({"error": str(e)}, status_code=500)


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


def register_routes(app: FastAPI, log_buffer: deque = None) -> None:
    # WHY: Attacher le buffer à l'app state évite les imports circulaires dans le monitoring.
    if log_buffer is not None:
        app.state.log_buffer = log_buffer
    app.include_router(router)
    app.include_router(admin_router)
    app.include_router(media_router)
    app.include_router(monitoring_router)
