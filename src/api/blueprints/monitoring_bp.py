"""Router monitoring — /api/monitoring/*"""
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.api.auth import require_monitoring
from src.monitoring.tracker import get_stats

monitoring_router = APIRouter()


class ReformulationToggleBody(BaseModel):
    enabled: bool


@monitoring_router.get("/api/monitoring/stats")
async def monitoring_stats(request: Request):
    require_monitoring(request)
    return get_stats()


@monitoring_router.get("/api/monitoring/pipeline")
async def monitoring_pipeline(request: Request):
    require_monitoring(request)
    try:
        from src.search.search import get_pipeline_stats
        stats = get_pipeline_stats()
        try:
            from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
            info = _get_client().get_collection(_COLLECTION_NAME)
            stats["qdrant_vectors"] = info.points_count or 0
            vp = info.config.params.vectors
            if hasattr(vp, "size"):
                stats["qdrant_dimensions"] = vp.size
            elif isinstance(vp, dict):
                first = next(iter(vp.values()), None)
                stats["qdrant_dimensions"] = first.size if first and hasattr(first, "size") else "?"
            else:
                stats["qdrant_dimensions"] = "?"
        except Exception as e:
            stats["qdrant_vectors"] = None
            stats["qdrant_dimensions"] = str(e)[:60]
        return stats
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@monitoring_router.get("/api/monitoring/reformulation")
async def monitoring_reformulation(request: Request):
    require_monitoring(request)
    from src.generation.generator import get_reformulation_enabled
    return {"enabled": get_reformulation_enabled()}


@monitoring_router.post("/api/monitoring/reformulation")
async def monitoring_set_reformulation(body: ReformulationToggleBody, request: Request):
    require_monitoring(request)
    from src.generation.generator import set_reformulation_enabled
    enabled = set_reformulation_enabled(body.enabled)
    return {"ok": True, "enabled": enabled}


@monitoring_router.get("/api/monitoring/reformulation/history")
async def monitoring_reformulation_history(request: Request):
    require_monitoring(request)
    from src.generation.generator import get_reformulation_history
    return {"history": get_reformulation_history()}


@monitoring_router.get("/api/monitoring/search-switches")
async def monitoring_search_switches(request: Request):
    require_monitoring(request)
    from src.search.search import get_runtime_switches
    return {"read_only": True, "switches": get_runtime_switches()}


@monitoring_router.get("/api/monitoring/runtime-profile")
async def monitoring_runtime_profile(request: Request):
    require_monitoring(request)
    from src.config.features import get_runtime_profile
    return get_runtime_profile()


@monitoring_router.get("/api/monitoring/contextual-retrieval")
async def monitoring_contextual_retrieval(request: Request):
    require_monitoring(request)
    try:
        from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
        client = _get_client()
        # Échantillon de 20 points pour vérifier combien ont un doc_summary
        results = client.scroll(
            collection_name=_COLLECTION_NAME,
            limit=50,
            with_payload=True,
            with_vectors=False,
        )
        points = results[0]
        total = len(points)
        with_context = sum(
            1 for p in points
            if p.payload.get("metadata", {}).get("doc_summary")
            or p.payload.get("doc_summary")  # fallback: LangChain may flatten metadata
        )
        # Debug: expose sample payload keys to help diagnose structure
        sample_keys = list(points[0].payload.keys()) if points else []
        sample_meta_keys = list(points[0].payload.get("metadata", {}).keys()) if points else []
        return {
            "sample_size": total,
            "with_contextual_summary": with_context,
            "coverage_pct": round(with_context / total * 100) if total else 0,
            "status": "✅ Actif" if with_context > 0 else "⚠️ Aucun contexte trouvé — relance un reindex",
            "debug_payload_keys": sample_keys,
            "debug_metadata_keys": sample_meta_keys,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@monitoring_router.get("/api/monitoring/features")
async def monitoring_features(request: Request):
    require_monitoring(request)
    features = {}

    # Vector Search
    try:
        from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
        info = _get_client().get_collection(_COLLECTION_NAME)
        features["vector"] = {"ok": True, "detail": f"{info.points_count or 0} vecteurs"}
    except Exception as e:
        features["vector"] = {"ok": False, "detail": str(e)[:60]}

    # BM25
    try:
        from src.search.search import get_pipeline_stats
        stats = get_pipeline_stats()
        loaded = stats.get("bm25_loaded", False)
        chunks = stats.get("bm25_chunks", 0)
        features["bm25"] = {"ok": bool(loaded and chunks), "detail": f"{chunks} chunks" if loaded else "Non chargé"}
    except Exception as e:
        features["bm25"] = {"ok": False, "detail": str(e)[:60]}

    # Reranker
    try:
        from src.search.search import get_runtime_switches
        sw = get_runtime_switches()
        hyde = bool(sw.get("hyde_enabled", False))
        rr = bool(sw.get("reranker_enabled", False))
        sr = bool(sw.get("smart_rerank_enabled", False))
        features["reranker"] = {"ok": rr, "detail": "Actif" if rr else "Désactivé (runtime)", "smart": sr}
        features["hyde"] = {"ok": hyde, "detail": "Actif" if hyde else "Désactivé (runtime)"}
    except Exception as e:
        features["reranker"] = {"ok": False, "detail": str(e)[:60]}
        features["hyde"] = {"ok": False, "detail": str(e)[:60]}

    # Contextual Retrieval
    try:
        from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
        client = _get_client()
        results = client.scroll(collection_name=_COLLECTION_NAME, limit=50, with_payload=True, with_vectors=False)
        points = results[0]
        with_ctx = sum(1 for p in points if p.payload.get("metadata", {}).get("doc_summary") or p.payload.get("doc_summary"))
        pct = round(with_ctx / len(points) * 100) if points else 0
        features["contextual"] = {"ok": with_ctx > 0, "detail": f"{pct}% des chunks enrichis ({with_ctx}/{len(points)})"}
    except Exception as e:
        features["contextual"] = {"ok": False, "detail": str(e)[:60]}

    # Reformulation
    try:
        from src.generation.generator import get_reformulation_enabled
        enabled = get_reformulation_enabled()
        features["reformulation"] = {"ok": True, "detail": "Activée" if enabled else "Désactivée (toggle possible)"}
    except Exception as e:
        features["reformulation"] = {"ok": False, "detail": str(e)[:60]}

    # PII Masking
    try:
        from src.security.pii_masker import masquer
        test = masquer("email: test@test.com")
        ok = "test@test.com" not in test
        features["pii"] = {"ok": ok, "detail": "Regex actif" if ok else "Masquage non fonctionnel"}
    except Exception as e:
        features["pii"] = {"ok": False, "detail": str(e)[:60]}

    # LLM-as-Judge (géré par Langfuse)
    features["judge"] = {"ok": True, "detail": "Délégué à Langfuse"}

    # Feedback
    try:
        from src.monitoring.tracker import _get_client as get_supa
        client = get_supa()
        features["feedback"] = {"ok": client is not None, "detail": "Supabase connecté" if client else "Supabase non configuré"}
    except Exception as e:
        features["feedback"] = {"ok": False, "detail": str(e)[:60]}

    # Confidence scores
    features["confidence"] = {"ok": features.get("bm25", {}).get("ok", False), "detail": "Via RRF scores"}

    # Watchdog
    try:
        from src.ingestion.watcher import _watcher
        running = _watcher._observer is not None and _watcher._observer.is_alive()
        features["watchdog"] = {"ok": running, "detail": "Observer actif" if running else "Non démarré"}
    except Exception as e:
        features["watchdog"] = {"ok": False, "detail": str(e)[:60]}

    # Vector Memory
    try:
        from src.memory.vector_memory import _get_client as get_mem_client
        cl = get_mem_client()
        features["memory"] = {"ok": cl is not None, "detail": "Qdrant connecté"}
    except Exception as e:
        features["memory"] = {"ok": False, "detail": str(e)[:60]}

    # TTS
    try:
        import edge_tts
        features["tts"] = {"ok": True, "detail": "edge-tts chargé"}
    except Exception as e:
        features["tts"] = {"ok": False, "detail": "edge-tts non installé"}

    # Multi-LLM Fallback
    try:
        primary_url = os.getenv("LLM_BASE_URL", "")
        fallback_key = bool(os.getenv("FALLBACK_API_KEY"))
        primary_name = "Cerebras" if "cerebras" in primary_url else ("Groq" if "groq" in primary_url else "LLM")
        providers = [primary_name]
        if fallback_key:
            fallback_url = os.getenv("FALLBACK_BASE_URL", "")
            fallback_name = "Groq" if "groq" in fallback_url else ("Cerebras" if "cerebras" in fallback_url else "Fallback")
            providers.append(fallback_name)
        features["fallback"] = {"ok": fallback_key, "detail": " → ".join(providers)}
    except Exception as e:
        features["fallback"] = {"ok": False, "detail": str(e)[:60]}

    return features


@monitoring_router.get("/api/monitoring/user-memories")
async def monitoring_user_memories(request: Request):
    require_monitoring(request)
    try:
        from src.monitoring.tracker import _get_client
        client = _get_client()
        if not client:
            return {"memories": [], "error": "Supabase non configuré"}
        r = client.table("user_memory").select("user_id, summary, updated_at").order("updated_at", desc=True).limit(20).execute()
        return {"memories": r.data or []}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@monitoring_router.get("/api/monitoring/feedbacks")
async def monitoring_feedbacks(request: Request, limit: int = 50):
    require_monitoring(request)
    try:
        from src.monitoring.tracker import get_recent_feedback_events

        return {"feedbacks": get_recent_feedback_events(limit=limit)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@monitoring_router.get("/api/monitoring/pii")
async def monitoring_pii(request: Request):
    require_monitoring(request)
    from src.security.pii_masker import get_pii_history
    return {"history": get_pii_history()}
