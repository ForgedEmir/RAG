"""Pipeline de recherche hybride : vectorielle (Qdrant) + BM25, fusion RRF, reranking cross-encoder.
Router adaptatif : active reranker + expansion uniquement sur les requêtes complexes.
Cache TTL en mémoire (évite de recalculer pour la même question).
"""
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional

from rank_bm25 import BM25Okapi
from src.ingestion.vector_store import get_store, search

logger = logging.getLogger(__name__)

_BM25_CORPUS_FILE = os.path.join(os.path.dirname(__file__), "..", "ingestion", "qdrant_db", "bm25_corpus.json")
_CACHE_TTL  = int(os.getenv("SEARCH_CACHE_TTL",  "300"))
_CACHE_SIZE = int(os.getenv("SEARCH_CACHE_SIZE", "100"))
_search_cache: dict = {}

_RERANKER_ENABLED        = os.getenv("RERANKER_ENABLED",        "true").lower()  != "false"
_QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "false").lower() != "false"
_RERANKER_MODEL          = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

_COMPLEX_SIGNALS = {
    "comment", "pourquoi", "différence", "difference", "compare", "comparer",
    "explique", "décris", "décrit", "liste", "relation", "lien", "entre",
    "quelles", "quels", "quelles sont", "quels sont", "raconte",
}

_pipeline_stats: dict = {
    "total_queries": 0, "cache_hits": 0, "cache_misses": 0,
    "simple_queries": 0, "complex_queries": 0, "reranker_calls": 0,
    "bm25_active": 0, "last_query": None, "last_mode": None,
    "last_vector_count": 0, "last_bm25_count": 0,
}

_bm25_index:  Optional[BM25Okapi] = None
_bm25_corpus: List[dict]          = []
_bm25_loaded: bool                = False

_reranker = None


# ── Cache ──────────────────────────────────────────────────────────────────────

def _cache_key(q: str) -> str:
    return hashlib.md5(q.lower().strip().encode()).hexdigest()

def _get_cache(q: str):
    e = _search_cache.get(_cache_key(q))
    if e and (time.time() - e[0]) < _CACHE_TTL:
        return e[1], e[2]
    return None

def _set_cache(q: str, passages: List[str], sources: List[str]) -> None:
    if len(_search_cache) >= _CACHE_SIZE:
        del _search_cache[min(_search_cache, key=lambda k: _search_cache[k][0])]
    _search_cache[_cache_key(q)] = (time.time(), passages, sources)

def invalidate_search_cache() -> None:
    _search_cache.clear()
    logger.info("Cache de recherche invalidé.")


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
    use_expansion: bool
    use_reranker:  bool
    k_candidates:  int

def _route(question: str) -> _QueryPlan:
    words = question.lower().split()
    is_complex = len(words) >= 6 or bool(set(words) & _COMPLEX_SIGNALS)
    return _QueryPlan(
        use_expansion=is_complex and _QUERY_EXPANSION_ENABLED,
        use_reranker=is_complex and _RERANKER_ENABLED,
        k_candidates=10 if is_complex else 5,
    )


# ── Reranker ──────────────────────────────────────────────────────────────────

def _get_reranker():
    global _reranker
    if _reranker is None and _RERANKER_ENABLED:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(_RERANKER_MODEL)
            logger.info(f"Reranker chargé : {_RERANKER_MODEL}")
        except Exception as e:
            logger.warning(f"Reranker indisponible : {e}")
    return _reranker

def _rerank(query: str, docs: List[dict]) -> List[dict]:
    reranker = _get_reranker()
    if not reranker or not docs:
        return docs
    try:
        scores = reranker.predict([[query, d["text"]] for d in docs])
        return [d for d, _ in sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)]
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
        logger.warning("Corpus BM25 introuvable — vector-only.")
        _bm25_loaded = True
        return
    with open(path, "r", encoding="utf-8") as f:
        _bm25_corpus = json.load(f)
    if _bm25_corpus:
        _bm25_index = BM25Okapi([d["text"].lower().split() for d in _bm25_corpus])
        logger.info(f"BM25 chargé ({len(_bm25_corpus)} chunks).")
    _bm25_loaded = True

def invalidate_bm25_cache() -> None:
    global _bm25_loaded
    _bm25_loaded = False
    invalidate_search_cache()


# ── RRF ───────────────────────────────────────────────────────────────────────

def _rrf(vector: List[dict], bm25: List[dict], k: int = 60) -> List[dict]:
    scores, doc_map = {}, {}
    for rank, doc in enumerate(vector + bm25 if False else vector):
        doc_map[doc["id"]] = doc
        scores[doc["id"]] = scores.get(doc["id"], 0) + 1 / (k + rank)
    for rank, doc in enumerate(bm25):
        doc_map[doc["id"]] = doc
        scores[doc["id"]] = scores.get(doc["id"], 0) + 1 / (k + rank)
    return [doc_map[i] for i in sorted(scores, key=lambda x: scores[x], reverse=True)]


# ── Pipeline ──────────────────────────────────────────────────────────────────

def rechercher_passages(question: str) -> Tuple[List[str], List[str]]:
    """Pipeline : cache → router → [expansion] → vector + BM25 → RRF → [reranker].
    Retourne (passages, sources).
    """
    _pipeline_stats["total_queries"] += 1
    cached = _get_cache(question)
    if cached:
        _pipeline_stats["cache_hits"] += 1
        return cached
    _pipeline_stats["cache_misses"] += 1

    plan = _route(question)
    _pipeline_stats["complex_queries" if plan.use_reranker or plan.k_candidates == 10 else "simple_queries"] += 1

    queries = _expand_query(question) if plan.use_expansion else [question]

    store = get_store()
    seen: set = set()
    vector_results: List[dict] = []
    for q in queries:
        for doc in search(store, q, k=5):
            doc_id = doc.metadata.get("chunk_id", doc.page_content[:80])
            if doc_id not in seen:
                seen.add(doc_id)
                vector_results.append({"id": doc_id, "text": doc.page_content,
                                       "fichier": doc.metadata.get("fichier", "inconnu")})

    if not _bm25_loaded:
        _load_bm25()

    bm25_results: List[dict] = []
    if _bm25_index and _bm25_corpus:
        scores = _bm25_index.get_scores(question.lower().split())
        top    = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:5]
        bm25_results = [_bm25_corpus[i] for i in top if scores[i] > 0]

    combined = _rrf(vector_results, bm25_results)[:plan.k_candidates] if bm25_results else vector_results[:plan.k_candidates]

    if plan.use_reranker:
        _pipeline_stats["reranker_calls"] += 1
        combined = _rerank(question, combined)

    combined = combined[:5]
    passages = [d["text"] for d in combined]
    sources  = list(dict.fromkeys(d["fichier"] for d in combined))

    _set_cache(question, passages, sources)

    mode = "complex" if plan.use_expansion or plan.use_reranker else "simple"
    if bm25_results:
        _pipeline_stats["bm25_active"] += 1
    _pipeline_stats.update(last_query=question[:80], last_mode=mode,
                           last_vector_count=len(vector_results), last_bm25_count=len(bm25_results))
    logger.info(f"[{mode}] '{question[:60]}' → {len(passages)} passage(s) "
                f"(v:{len(vector_results)}, bm25:{len(bm25_results)}, reranker:{plan.use_reranker})")
    return passages, sources
