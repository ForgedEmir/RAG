"""Pipeline de recherche hybride : vectorielle (Qdrant) + BM25, fusion RRF, reranking ONNX.
Router adaptatif : active reranker + expansion uniquement sur les requêtes complexes.
Cache TTL Redis (partagé entre workers) avec fallback mémoire si Redis indisponible.
"""
import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from rank_bm25 import BM25Okapi
from src.config.features import env_bool
from src.ingestion.vector_store import get_store, search

logger = logging.getLogger(__name__)

_BM25_CORPUS_FILE = os.path.join(os.path.dirname(__file__), "..", "ingestion", "qdrant_db", "bm25_corpus.json")
_CACHE_TTL   = int(os.getenv("SEARCH_CACHE_TTL",  "300"))
_CACHE_SIZE  = int(os.getenv("SEARCH_CACHE_SIZE", "100"))

# Constantes nommées — évite les magic numbers dispersés dans le code
RRF_K              = 60    # Paramètre de fusion RRF standard
CANDIDATES_COMPLEX = max(8, int(os.getenv("SEARCH_COMPLEX_CANDIDATES", "14")))
CANDIDATES_SIMPLE  = max(3, int(os.getenv("SEARCH_SIMPLE_CANDIDATES", "5")))
RERANKER_TOP_N     = max(3, int(os.getenv("RERANKER_TOP_N", "6")))
FINAL_TOP_N        = max(1, int(os.getenv("SEARCH_FINAL_TOP_N", "4")))
BM25_FALLBACK_MIN  = 3     # Seuil vecteur en dessous duquel BM25 est activé

# WHY: Les scores RRF max = 1/(60+0) ≈ 0.016, donc le seuil doit être en échelle RRF.
# 0.005 correspond à un score si bas qu'aucun document pertinent n'a été trouvé.
_HYDE_THRESHOLD = float(os.getenv("HYDE_SCORE_THRESHOLD", "0.005"))
_HYDE_ENABLED            = env_bool("HYDE_ENABLED", True)
_RERANKER_ENABLED        = env_bool("RERANKER_ENABLED", True)
_QUERY_EXPANSION_ENABLED = env_bool("QUERY_EXPANSION_ENABLED", False)
_RERANKER_MODEL          = os.getenv("RERANKER_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
_RERANKER_MAX_INPUT      = max(2, int(os.getenv("RERANKER_MAX_INPUT", "6")))
_MIN_VECTOR_BEFORE_BM25  = max(1, int(os.getenv("MIN_VECTOR_BEFORE_BM25", str(BM25_FALLBACK_MIN))))
_SMART_RERANK_ENABLED    = env_bool("SMART_RERANK_ENABLED", True)
_SMART_RERANK_TOP1_MIN   = float(os.getenv("SMART_RERANK_TOP1_MIN", "0.014"))
_SMART_RERANK_GAP_MIN    = float(os.getenv("SMART_RERANK_GAP_MIN", "0.01"))
_RERANK_SIMPLE_QUERIES   = env_bool("RERANK_SIMPLE_QUERIES", False)

_COMPLEX_SIGNALS = {
    "comment", "pourquoi", "différence", "difference", "compare", "comparer",
    "explique", "décris", "décrit", "liste", "relation", "lien", "entre",
    "quelles", "quels", "quelles sont", "quels sont", "raconte",
}

_RERANK_REASONING_SIGNALS = {
    "pourquoi", "comment", "compare", "comparer", "difference", "différence",
    "relation", "lien", "entre", "vs", "versus", "explique", "expliquer",
}

_pipeline_stats: dict = {
    "total_queries": 0, "cache_hits": 0, "cache_misses": 0,
    "simple_queries": 0, "complex_queries": 0, "reranker_calls": 0,
    "bm25_active": 0, "last_query": None, "last_mode": None,
    "last_vector_count": 0, "last_bm25_count": 0,
}


def get_runtime_switches() -> dict:
    return {
        "hyde_enabled": _HYDE_ENABLED,
        "reranker_enabled": _RERANKER_ENABLED,
        "rerank_simple_queries": _RERANK_SIMPLE_QUERIES,
        "reranker_model": _RERANKER_MODEL,
        "reranker_max_input": _RERANKER_MAX_INPUT,
        "query_expansion_enabled": _QUERY_EXPANSION_ENABLED,
        "smart_rerank_enabled": _SMART_RERANK_ENABLED,
        "smart_rerank_top1_min": _SMART_RERANK_TOP1_MIN,
        "smart_rerank_gap_min": _SMART_RERANK_GAP_MIN,
    }

# ── Redis cache (partagé entre workers) avec fallback mémoire ────────────────
_redis_client = None
_redis_lock   = threading.Lock()

def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    with _redis_lock:
        if _redis_client is None:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                try:
                    import redis
                    _redis_client = redis.from_url(redis_url, decode_responses=False, socket_connect_timeout=2)
                    _redis_client.ping()
                    logger.info("[CACHE] Redis connecté.")
                except Exception as e:
                    logger.warning(f"[CACHE] Redis indisponible, fallback mémoire : {e}")
                    _redis_client = None
    return _redis_client

_search_cache: dict = {}  # fallback mémoire si Redis indisponible
_cache_lock         = threading.Lock()

_bm25_index:  Optional[BM25Okapi] = None
_bm25_corpus: List[dict]          = []
_bm25_loaded: bool                = False
_bm25_lock                        = threading.Lock()

_reranker     = None
_reranker_lock = threading.Lock()


# ── Cache Redis + fallback mémoire ────────────────────────────────────────────

_CACHE_PREFIX = "lk:search:"

def _cache_key(q: str) -> str:
    return _CACHE_PREFIX + hashlib.md5(q.lower().strip().encode()).hexdigest()

def _get_cache(q: str):
    key = _cache_key(q)
    r = _get_redis()
    if r:
        try:
            raw = r.get(key)
            if raw:
                data = json.loads(raw)
                return data["passages"], data["sources"], data["scores"]
            return None
        except Exception:
            pass
    # Fallback mémoire
    with _cache_lock:
        e = _search_cache.get(key)
        if e and (time.time() - e[0]) < _CACHE_TTL:
            return e[1], e[2], e[3]
    return None

def _set_cache(q: str, passages: List[str], sources: List[str], scores: List[float]) -> None:
    key = _cache_key(q)
    r = _get_redis()
    if r:
        try:
            r.setex(key, _CACHE_TTL, json.dumps({"passages": passages, "sources": sources, "scores": scores}))
            return
        except Exception:
            pass
    # Fallback mémoire
    with _cache_lock:
        if len(_search_cache) >= _CACHE_SIZE:
            del _search_cache[min(_search_cache, key=lambda k: _search_cache[k][0])]
        _search_cache[key] = (time.time(), passages, sources, scores)

def invalidate_search_cache() -> None:
    r = _get_redis()
    if r:
        try:
            keys = r.keys(_CACHE_PREFIX + "*")
            if keys:
                r.delete(*keys)
        except Exception:
            pass
    with _cache_lock:
        _search_cache.clear()
    logger.info("[CACHE] Cache de recherche invalidé.")


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_pipeline_stats() -> dict:
    return {
        **_pipeline_stats,
        "cache_size":       len(_search_cache),
        "bm25_chunks":      len(_bm25_corpus),
        "bm25_loaded":      _bm25_loaded and _bm25_index is not None,
        "reranker_enabled": _RERANKER_ENABLED,
        "cache_hit_rate":   round(_pipeline_stats["cache_hits"] / max(_pipeline_stats["total_queries"], 1) * 100),
    }


# ── Router ────────────────────────────────────────────────────────────────────

@dataclass
class _QueryPlan:
    is_complex: bool
    use_expansion: bool
    use_reranker:  bool
    k_candidates:  int

def _route(question: str) -> _QueryPlan:
    words = question.lower().split()
    is_complex = len(words) >= 6 or bool(set(words) & _COMPLEX_SIGNALS)
    return _QueryPlan(
        is_complex=is_complex,
        use_expansion=is_complex and _QUERY_EXPANSION_ENABLED,
        use_reranker=_RERANKER_ENABLED,
        k_candidates=CANDIDATES_COMPLEX if is_complex else CANDIDATES_SIMPLE,
    )


def _needs_reasoning_rerank(question: str) -> bool:
    q = question.lower()
    return any(sig in q for sig in _RERANK_REASONING_SIGNALS)


def _should_apply_reranker(plan: _QueryPlan, combined: List[dict], rrf_scores: dict, question: str) -> bool:
    if not plan.use_reranker:
        return False
    if not plan.is_complex and not _RERANK_SIMPLE_QUERIES:
        return False
    if not _SMART_RERANK_ENABLED:
        return True
    if not combined:
        return False

    raw_scores = [rrf_scores.get(d["id"], 0.0) for d in combined]
    top1_raw = raw_scores[0] if raw_scores else 0.0
    if top1_raw <= 0:
        return True
    top2_raw = raw_scores[1] if len(raw_scores) > 1 else 0.0
    relative_gap = (top1_raw - top2_raw) / max(top1_raw, 1e-9)

    # Questions longues mais factuelles peuvent se passer du reranker si le top-1
    # est solide et que le gap est correct.
    needs_reasoning = _needs_reasoning_rerank(question)
    score_threshold = _SMART_RERANK_TOP1_MIN
    gap_threshold = _SMART_RERANK_GAP_MIN
    if plan.is_complex and needs_reasoning:
        gap_threshold = max(gap_threshold, 0.02)

    return top1_raw < score_threshold or relative_gap < gap_threshold


# ── Reranker ONNX (FastEmbed — zéro PyTorch) ─────────────────────────────────

def _get_reranker():
    """Charge le cross-encoder ONNX via fastembed. Thread-safe, singleton."""
    global _reranker
    if _reranker is not None or not _RERANKER_ENABLED:
        return _reranker
    with _reranker_lock:
        if _reranker is not None:
            return _reranker
        try:
            from fastembed import TextEmbedding  # noqa: F401 — vérifie que fastembed est dispo
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            _reranker = TextCrossEncoder(model_name=_RERANKER_MODEL)
            logger.info(f"Reranker ONNX chargé : {_RERANKER_MODEL}")
        except Exception as e:
            logger.warning(f"Reranker ONNX indisponible : {e} — RRF seul actif.")
    return _reranker


def _rerank(query: str, docs: List[dict]) -> List[dict]:
    reranker = _get_reranker()
    if not reranker or not docs:
        return docs
    try:
        if len(docs) > _RERANKER_MAX_INPUT:
            logger.info(
                "reranker input capped: %s -> %s docs",
                len(docs),
                _RERANKER_MAX_INPUT,
            )
        docs_to_rerank = docs[:_RERANKER_MAX_INPUT]
        passages = [d["text"] for d in docs_to_rerank]
        scores   = list(reranker.rerank(query, passages))
        # scores est un itérateur de floats dans l'ordre des passages
        ranked   = sorted(zip(docs_to_rerank, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked][:RERANKER_TOP_N]
    except Exception as e:
        logger.warning(f"Reranking échoué : {e}")
        return docs


# ── Query expansion ───────────────────────────────────────────────────────────

def _expand_query(question: str) -> List[str]:
    try:
        from src.generation.generator import _llm
        from langchain_core.messages import SystemMessage, HumanMessage
        if not _llm:
            return [question]
        result = _llm.invoke([
            SystemMessage(content=(
                "Génère exactement 2 reformulations de la question pour chercher dans une base de lore fantastique. "
                "Une par ligne, sans numérotation ni explication."
            )),
            HumanMessage(content=question),
        ])
        variants = [q.strip() for q in result.content.strip().splitlines() if q.strip()]
        return [question] + variants[:2]
    except Exception as e:
        logger.warning(f"Query expansion échouée : {e}")
        return [question]


# ── BM25 ──────────────────────────────────────────────────────────────────────

def _load_bm25() -> None:
    global _bm25_index, _bm25_corpus, _bm25_loaded
    path = os.path.normpath(_BM25_CORPUS_FILE)
    if not os.path.exists(path):
        logger.warning("Corpus BM25 introuvable — vector-only (retry au prochain appel).")
        return
    with _bm25_lock:
        if _bm25_loaded:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            _bm25_corpus = data if isinstance(data, list) else []
            if _bm25_corpus:
                _bm25_index = BM25Okapi([d["text"].lower().split() for d in _bm25_corpus if "text" in d])
                logger.info(f"BM25 chargé ({len(_bm25_corpus)} chunks).")
            _bm25_loaded = True
        except json.JSONDecodeError as e:
            logger.warning(f"Corpus BM25 corrompu ({e}) — vector-only.")
        except Exception as e:
            logger.warning(f"Chargement BM25 impossible ({e}) — vector-only.")

def invalidate_bm25_cache() -> None:
    global _bm25_loaded
    with _bm25_lock:
        _bm25_loaded = False
    invalidate_search_cache()


# ── RRF avec scores exposés ───────────────────────────────────────────────────

def _rrf(vector: List[dict], bm25: List[dict], k: int = RRF_K) -> Tuple[List[dict], dict]:
    """Retourne (docs_triés, {id: score}) pour que le caller puisse calculer la confiance."""
    scores, doc_map = {}, {}
    for rank, doc in enumerate(vector):
        doc_map[doc["id"]] = doc
        scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1 / (k + rank)
    for rank, doc in enumerate(bm25):
        doc_map[doc["id"]] = doc
        scores[doc["id"]] = scores.get(doc["id"], 0.0) + 1 / (k + rank)
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [doc_map[i] for i in sorted_ids], {i: scores[i] for i in sorted_ids}


# ── Pipeline ──────────────────────────────────────────────────────────────────

def rechercher_passages(question: str) -> Tuple[List[str], List[str], List[float]]:
    """Pipeline : cache → router → [expansion] → vector + BM25 → RRF → [reranker].
    Retourne (passages, sources, confidence_scores).
    confidence_scores : liste de scores normalisés [0.0–1.0] pour chaque passage.
    """
    _pipeline_stats["total_queries"] += 1
    cached = _get_cache(question)
    if cached:
        _pipeline_stats["cache_hits"] += 1
        return cached  # passages, sources, scores
    _pipeline_stats["cache_misses"] += 1

    plan = _route(question)
    _pipeline_stats["complex_queries" if plan.use_reranker or plan.k_candidates == CANDIDATES_COMPLEX else "simple_queries"] += 1

    queries = _expand_query(question) if plan.use_expansion else [question]

    store = get_store()
    seen: set = set()
    vector_results: List[dict] = []
    t_vec = time.time()
    try:
        for q in queries:
            for doc in search(store, q, k=plan.k_candidates):
                doc_id = doc.metadata.get("chunk_id", doc.page_content[:80])
                if doc_id not in seen:
                    seen.add(doc_id)
                    vector_results.append({
                        "id": doc_id, "text": doc.page_content,
                        "fichier": doc.metadata.get("fichier", "inconnu"),
                        "parent_id": doc.metadata.get("parent_id"),
                        "chunk_type": doc.metadata.get("chunk_type", "standard"),
                    })
    except Exception as e:
        logger.warning(f"Vector search failed ({int((time.time()-t_vec)*1000)}ms): {e}")
    logger.info(f"vector={int((time.time()-t_vec)*1000)}ms ({len(vector_results)} docs)")

    if not _bm25_loaded:
        _load_bm25()

    bm25_results: List[dict] = []
    run_bm25 = len(vector_results) < _MIN_VECTOR_BEFORE_BM25
    if _bm25_index and _bm25_corpus and run_bm25:
        bm25_scores = _bm25_index.get_scores(question.lower().split())
        top         = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:CANDIDATES_SIMPLE]
        bm25_results = [_bm25_corpus[i] for i in top if bm25_scores[i] > 0]

    if bm25_results:
        combined, rrf_scores = _rrf(vector_results, bm25_results)
        combined = combined[:plan.k_candidates]
    else:
        # Pas de BM25 → on crée des faux scores RRF pour la cohérence
        combined = vector_results[:plan.k_candidates]
        rrf_scores = {d["id"]: 1 / (RRF_K + i) for i, d in enumerate(combined)}

    # Deduplication par fichier source : ne garde que le meilleur passage par fichier
    # Empêche qu'un fichier avec beaucoup de mentions mineures écrase le fichier principal
    seen_files: dict = {}
    for doc in combined:
        fichier = doc.get("fichier", "inconnu")
        score = rrf_scores.get(doc["id"], 0.0)
        if fichier not in seen_files or score > rrf_scores.get(seen_files[fichier]["id"], 0.0):
            seen_files[fichier] = doc
    combined = sorted(seen_files.values(), key=lambda d: rrf_scores.get(d["id"], 0.0), reverse=True)

    should_rerank = _should_apply_reranker(plan, combined, rrf_scores, question)
    if should_rerank:
        _pipeline_stats["reranker_calls"] += 1
        t_rerank = time.time()
        combined = _rerank(question, combined)
        logger.info(f"reranker={int((time.time()-t_rerank)*1000)}ms")
    elif plan.use_reranker:
        logger.info("reranker=skipped (smart-rerank)" )

    # HyDE fallback: if enabled + no results or very low scores, try Hypothetical Document Embeddings
    if _HYDE_ENABLED and (not combined or (rrf_scores and max(rrf_scores.values()) < _HYDE_THRESHOLD)):
        logger.info(f"HyDE fallback triggered (max score {max(rrf_scores.values()) if rrf_scores else 0} < {_HYDE_THRESHOLD})")
        try:
            from src.retrieval.hyde import hyde_search
            hyde_store = get_store()
            embedder = hyde_store._embeddings if hasattr(hyde_store, "_embeddings") else None
            if embedder:
                hyde_docs = hyde_search(question, None, embedder, hyde_store, top_k=FINAL_TOP_N)
                combined = [{"id": d.metadata.get("chunk_id", d.page_content[:80]),
                             "text": d.page_content,
                             "fichier": d.metadata.get("fichier", "inconnu"),
                             "parent_id": d.metadata.get("parent_id")} for d in hyde_docs]
                rrf_scores = {d["id"]: 0.5 for d in combined}  # Neutral score for HyDE results
        except Exception as e:
            logger.warning(f"HyDE fallback failed: {e}")

    combined = combined[:FINAL_TOP_N]

    passages = [d["text"] for d in combined]
    sources  = list(dict.fromkeys(d["fichier"] for d in combined))

    # Normalisation des scores [0.0–1.0] pour le confidence score UI
    raw_scores  = [rrf_scores.get(d["id"], 0.0) for d in combined]
    max_score   = max(raw_scores, default=1.0) or 1.0
    conf_scores = [round(s / max_score, 3) for s in raw_scores]

    _set_cache(question, passages, sources, conf_scores)

    mode = "complex" if plan.is_complex else "simple"
    if bm25_results:
        _pipeline_stats["bm25_active"] += 1
    _pipeline_stats.update(last_query=question[:80], last_mode=mode,
                           last_vector_count=len(vector_results), last_bm25_count=len(bm25_results))
    logger.info(f"[{mode}] '{question[:60]}' → {len(passages)} passage(s) "
                f"(v:{len(vector_results)}, bm25:{len(bm25_results)}, reranker:{should_rerank})")
    return passages, sources, conf_scores
