"""
Hybrid search engine for the RAG system.
Combines vector search (Qdrant) and lexical search (BM25) with RRF (Reciprocal Rank Fusion).
Includes intelligent reranking via ONNX cross-encoders and a HyDE (Hypothetical Document Embeddings) fallback.
"""
import json
import logging
import os
import re
import tempfile
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple, Optional, Set, Dict, Any

from rank_bm25 import BM25Okapi
from src.config.features import env_bool
from src.ingestion.vector_store import get_store, search

logger = logging.getLogger(__name__)

# Path and cache constants
_BM25_CORPUS_FILE = os.path.join(os.path.dirname(__file__), "..", "ingestion", "qdrant_db", "bm25_corpus.json")
_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL", "300"))
_CACHE_SIZE = int(os.getenv("SEARCH_CACHE_SIZE", "100"))
_BM25_BOOTSTRAP_LIMIT = max(100, int(os.getenv("BM25_BOOTSTRAP_LIMIT", "512")))
_BM25_BOOTSTRAP_MAX_POINTS = max(500, int(os.getenv("BM25_BOOTSTRAP_MAX_POINTS", "50000")))
_BM25_BOOTSTRAP_RETRY_SECONDS = max(5, int(os.getenv("BM25_BOOTSTRAP_RETRY_SECONDS", "30")))

# Search pipeline algorithmic parameters
RRF_K = 60    # Standard parameter for Reciprocal Rank Fusion
CANDIDATES_COMPLEX = max(8, int(os.getenv("SEARCH_COMPLEX_CANDIDATES", "14")))
CANDIDATES_SIMPLE = max(3, int(os.getenv("SEARCH_SIMPLE_CANDIDATES", "5")))
RERANKER_TOP_N = max(3, int(os.getenv("RERANKER_TOP_N", "6")))
FINAL_TOP_N = max(1, int(os.getenv("SEARCH_FINAL_TOP_N", "6")))
BM25_FALLBACK_MIN = 3  # Minimum vector results before activating BM25

# Dynamic behaviour configuration
_HYDE_THRESHOLD = float(os.getenv("HYDE_SCORE_THRESHOLD", "0.005"))
_HYDE_ENABLED = env_bool("HYDE_ENABLED", True)
_RERANKER_ENABLED = env_bool("RERANKER_ENABLED", True)
_QUERY_EXPANSION_ENABLED = env_bool("QUERY_EXPANSION_ENABLED", False)
_RERANKER_MODEL = os.getenv("RERANKER_MODEL", "jinaai/jina-reranker-v2-base-multilingual")
_RERANKER_MAX_INPUT = max(2, int(os.getenv("RERANKER_MAX_INPUT", "6")))
_MIN_VECTOR_BEFORE_BM25 = max(1, int(os.getenv("MIN_VECTOR_BEFORE_BM25", str(BM25_FALLBACK_MIN))))
_SMART_RERANK_ENABLED = env_bool("SMART_RERANK_ENABLED", True)
_SMART_RERANK_TOP1_MIN = float(os.getenv("SMART_RERANK_TOP1_MIN", "0.014"))
_SMART_RERANK_GAP_MIN = float(os.getenv("SMART_RERANK_GAP_MIN", "0.01"))
_RERANK_SIMPLE_QUERIES = env_bool("RERANK_SIMPLE_QUERIES", False)
_BM25_FR_NORMALIZATION = env_bool("BM25_FR_NORMALIZATION", True)

# French stopwords for BM25
_BM25_FR_STOPWORDS = {
    "a", "ai", "as", "au", "aux", "avec", "ce", "ces", "cet", "cette",
    "comme", "dans", "de", "des", "du", "elle", "en", "et", "est", "il",
    "je", "la", "le", "les", "leur", "leurs", "lui", "ma", "mais", "me",
    "mes", "moi", "mon", "ne", "nos", "notre", "nous", "on", "ou", "par",
    "pas", "pour", "qu", "que", "qui", "sa", "se", "ses", "son", "sur",
    "ta", "te", "tes", "toi", "ton", "tu", "un", "une", "vos", "votre", "vous",
}

# Linguistic signals for query routing
_COMPLEX_SIGNALS = {
    "how", "why", "difference", "compare",
    "explain", "describe", "list", "relation", "link", "between",
    "what", "what are", "tell",
}

_RERANK_REASONING_SIGNALS = {
    "why", "how", "compare", "difference",
    "relation", "link", "between", "vs", "versus", "explain",
}

# Pipeline runtime statistics
_pipeline_stats: Dict[str, Any] = {
    "total_queries": 0, "cache_hits": 0, "cache_misses": 0,
    "simple_queries": 0, "complex_queries": 0, "reranker_calls": 0,
    "bm25_active": 0, "last_query": None, "last_mode": None,
    "last_vector_count": 0, "last_bm25_count": 0,
}


def get_runtime_switches() -> Dict[str, Any]:
    """Returns the current state of runtime configuration switches."""
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


# Global state (Singleton / Cache)
_bm25_index: Optional[BM25Okapi] = None
_bm25_corpus: List[Dict[str, Any]] = []
_bm25_loaded: bool = False
_bm25_lock = threading.Lock()
_bm25_bootstrap_lock = threading.Lock()
_bm25_last_bootstrap_try: float = 0.0
_bm25_missing_warned: bool = False

_reranker = None
_reranker_lock = threading.Lock()


def _tokenize_bm25(text: str) -> List[str]:
    """Tokenisation optimized for French (normalization, accents, stopwords)."""
    if not text:
        return []
    normalized = text.lower()
    if _BM25_FR_NORMALIZATION:
        normalized = unicodedata.normalize("NFKD", normalized)
        normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    tokens = re.findall(r"[a-z0-9]+", normalized)
    if _BM25_FR_NORMALIZATION:
        tokens = [t for t in tokens if t not in _BM25_FR_STOPWORDS and len(t) > 1]
    return tokens


def get_pipeline_stats() -> Dict[str, Any]:
    """Returns the performance statistics of the search pipeline."""
    return {
        **_pipeline_stats,
        "bm25_chunks":      len(_bm25_corpus),
        "bm25_loaded":      _bm25_loaded and _bm25_index is not None,
        "reranker_enabled": _RERANKER_ENABLED,
        "cache_hit_rate":   round(_pipeline_stats["cache_hits"] / max(_pipeline_stats["total_queries"], 1) * 100),
    }


@dataclass
class _QueryPlan:
    """Represents the search strategy decided by the router."""
    is_complex: bool
    use_expansion: bool
    use_reranker: bool
    k_candidates: int


def _route(question: str) -> _QueryPlan:
    """Analyses the question to determine complexity and search strategy."""
    words = question.lower().split()
    is_complex = len(words) >= 6 or bool(set(words) & _COMPLEX_SIGNALS)
    return _QueryPlan(
        is_complex=is_complex,
        use_expansion=is_complex and _QUERY_EXPANSION_ENABLED,
        use_reranker=_RERANKER_ENABLED,
        k_candidates=CANDIDATES_COMPLEX if is_complex else CANDIDATES_SIMPLE,
    )


def _needs_reasoning_rerank(question: str) -> bool:
    """Detects if the question requires complex reasoning that warrants deep reranking."""
    q = question.lower()
    return any(sig in q for sig in _RERANK_REASONING_SIGNALS)


def _should_apply_reranker(plan: _QueryPlan, combined: List[Dict], rrf_scores: Dict[str, float], question: str) -> bool:
    """Dynamically decides whether to call the reranker to optimise latency."""
    if not plan.use_reranker or not combined:
        return False
    if not plan.is_complex and not _RERANK_SIMPLE_QUERIES:
        return False
    if not _SMART_RERANK_ENABLED:
        return True

    raw_scores = [rrf_scores.get(d["id"], 0.0) for d in combined]
    top1_raw = raw_scores[0] if raw_scores else 0.0
    if top1_raw <= 0:
        return True
    top2_raw = raw_scores[1] if len(raw_scores) > 1 else 0.0
    relative_gap = (top1_raw - top2_raw) / max(top1_raw, 1e-9)

    needs_reasoning = _needs_reasoning_rerank(question)
    score_threshold = _SMART_RERANK_TOP1_MIN
    gap_threshold = _SMART_RERANK_GAP_MIN
    
    if plan.is_complex and needs_reasoning:
        gap_threshold = max(gap_threshold, 0.02)

    return top1_raw < score_threshold or relative_gap < gap_threshold


def _get_reranker():
    """Loads the ONNX cross-encoder (FastEmbed) in a thread-safe manner."""
    global _reranker
    if _reranker is not None or not _RERANKER_ENABLED:
        return _reranker
    with _reranker_lock:
        if _reranker is not None:
            return _reranker
        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            _reranker = TextCrossEncoder(model_name=_RERANKER_MODEL)
            logger.info(f"ONNX reranker loaded: {_RERANKER_MODEL}")
        except Exception as e:
            logger.warning(f"Failed to load ONNX reranker: {e}. Falling back to RRF only.")
    return _reranker


def _rerank(query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Applies semantic reranking on the top candidates via a cross-encoder."""
    reranker = _get_reranker()
    if not reranker or not docs:
        return docs
    try:
        docs_to_rerank = docs[:_RERANKER_MAX_INPUT]
        passages = [d["text"] for d in docs_to_rerank]
        scores = list(reranker.rerank(query, passages))
        ranked = sorted(zip(docs_to_rerank, scores), key=lambda x: x[1], reverse=True)
        return [d for d, _ in ranked][:RERANKER_TOP_N]
    except Exception as e:
        logger.warning(f"Reranking failed: {e}")
        return docs


async def _expand_query(question: str) -> List[str]:
    """Generates question variants via the LLM to improve recall."""
    try:
        from src.generation.generator import _llm
        from langchain_core.messages import SystemMessage, HumanMessage
        if not _llm:
            return [question]
        result = await _llm.ainvoke([
            SystemMessage(content=(
                "Generate exactly 2 reformulations of the question for searching a fantasy lore knowledge base. "
                "One per line, no numbering or explanation."
            )),
            HumanMessage(content=question),
        ])
        variants = [q.strip() for q in result.content.strip().splitlines() if q.strip()]
        return [question] + variants[:2]
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}")
        return [question]


def _load_bm25() -> None:
    """Loads or rebuilds the BM25 lexical index from the Qdrant corpus."""
    global _bm25_index, _bm25_corpus, _bm25_loaded, _bm25_missing_warned

    path = os.path.normpath(_BM25_CORPUS_FILE)
    if not os.path.exists(path):
        # Attempt dynamic rebuild if the corpus file is missing
        from src.ingestion.run import bootstrap_bm25_from_qdrant
        rebuilt = bootstrap_bm25_from_qdrant(path)
        if not rebuilt:
            if not _bm25_missing_warned:
                logger.warning("BM25 corpus missing. Vector-only mode.")
                _bm25_missing_warned = True
            return

    with _bm25_lock:
        if _bm25_loaded:
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            _bm25_corpus = data if isinstance(data, list) else []
            if _bm25_corpus:
                tokenized_corpus = [_tokenize_bm25(d.get("text", "")) or ["_empty_"] for d in _bm25_corpus]
                _bm25_index = BM25Okapi(tokenized_corpus)
                logger.info(f"BM25 index loaded ({len(_bm25_corpus)} fragments).")
            _bm25_loaded = True
        except Exception as e:
            logger.warning(f"Error loading BM25 index: {e}")


def invalidate_bm25_cache() -> None:
    """Resets the BM25 index to force a reload on next call."""
    global _bm25_index, _bm25_corpus, _bm25_loaded, _bm25_missing_warned
    with _bm25_lock:
        _bm25_index = None
        _bm25_corpus = []
        _bm25_loaded = False
        _bm25_missing_warned = False


def _rrf(vector: List[Dict], bm25: List[Dict], k: int = RRF_K) -> Tuple[List[Dict], Dict[str, float]]:
    """Combines vector and lexical results via Reciprocal Rank Fusion (RRF)."""
    scores, doc_map = {}, {}
    for rank, doc in enumerate(vector):
        doc_id = doc["id"]
        doc_map[doc_id] = doc
        scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank)
    for rank, doc in enumerate(bm25):
        doc_id = doc["id"]
        doc_map[doc_id] = doc
        scores[doc_id] = scores.get(doc_id, 0.0) + 1 / (k + rank)
    
    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [doc_map[i] for i in sorted_ids], {i: scores[i] for i in sorted_ids}


def _subject_key(filename: str) -> str:
    """Returns the subject prefix (before first _ or -) as a deduplication key."""
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    return re.split(r"[_\-]", stem)[0]


def _resolve_conflicts_by_recency(docs: List[Dict]) -> Tuple[List[Dict], Set[str]]:
    """Resolves conflicts between versions of the same subject, keeping the most recent."""
    if len(docs) < 2:
        return docs, set()

    max_by_subject = {}
    count_at_max = {}
    for d in docs:
        subject = _subject_key(d.get("filename", "unknown"))
        ts = float(d.get("indexed_at", 0.0) or 0.0)
        if subject not in max_by_subject or ts > max_by_subject[subject]:
            max_by_subject[subject] = ts
            count_at_max[subject] = 1
        elif ts == max_by_subject[subject]:
            count_at_max[subject] = count_at_max.get(subject, 1) + 1

    tie_subjects = {s for s, cnt in count_at_max.items() if cnt > 1}
    kept = [d for d in docs if float(d.get("indexed_at", 0.0) or 0.0) >= max_by_subject[_subject_key(d.get("filename", "unknown"))]]
    return kept, tie_subjects


async def search_passages(question: str, tenant_id: str = "") -> Tuple[List[str], List[str], List[float], Set[str]]:
    """
    Main hybrid search pipeline.
    Runs vector search, lexical search, RRF fusion, reranking, and HyDE fallback.

    Args:
        question: The user's question.
        tenant_id: Qdrant tenant filter for B2B multi-tenant isolation.

    Returns:
        Tuple: (text_passages, source_files, confidence_scores, conflicting_subjects)
    """
    _pipeline_stats["total_queries"] += 1
    plan = _route(question)
    
    # Step 1: Vector search (multi-query if expansion is active)
    queries = await _expand_query(question) if plan.use_expansion else [question]
    store = get_store()
    seen_ids = set()
    vector_results = []
    
    for q in queries:
        for doc in search(store, q, k=plan.k_candidates, tenant_id=tenant_id):
            doc_id = doc.metadata.get("chunk_id", doc.page_content[:80])
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                # WHY: Use original_text for LLM generation when present
                # to avoid polluting the prompt with late-chunking context.
                # page_content is still used by the reranker.
                text_for_llm = doc.metadata.get("original_text", doc.page_content)
                vector_results.append({
                    "id": doc_id,
                    "text": text_for_llm,
                    "raw_content": doc.page_content,
                    # Read both keys: "fichier" is the legacy/current ingestion key,
                    # "filename" is the EN-translated alias from features/misc.
                    "filename": doc.metadata.get("filename") or doc.metadata.get("fichier", "unknown"),
                    "indexed_at": float(doc.metadata.get("indexed_at", 0.0) or 0.0),
                })

    # Step 2: BM25 lexical search (if needed)
    if not _bm25_loaded:
        _load_bm25()

    bm25_results = []
    if _bm25_index and _bm25_corpus:
        query_tokens = _tokenize_bm25(question)
        if query_tokens:
            bm25_scores = _bm25_index.get_scores(query_tokens)
            top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:plan.k_candidates]
            # Normalize each corpus entry so downstream code can read `filename`
            # regardless of whether the corpus was written with "fichier" (FR) or "filename" (EN).
            bm25_results = []
            for i in top_indices:
                if bm25_scores[i] > 0:
                    entry = dict(_bm25_corpus[i])
                    entry["filename"] = entry.get("filename") or entry.get("fichier", "unknown")
                    bm25_results.append(entry)

    # Step 3: RRF fusion
    if bm25_results:
        combined, rrf_scores = _rrf(vector_results, bm25_results)
        combined = combined[:plan.k_candidates]
    else:
        combined = vector_results[:plan.k_candidates]
        rrf_scores = {d["id"]: 1 / (RRF_K + i) for i, d in enumerate(combined)}

    # Step 4: Deduplication and version resolution
    seen_files = {}
    for doc in combined:
        filename = doc.get("filename", "unknown")
        if filename not in seen_files or rrf_scores.get(doc["id"], 0.0) > rrf_scores.get(seen_files[filename]["id"], 0.0):
            seen_files[filename] = doc
    
    combined, tie_subjects = _resolve_conflicts_by_recency(list(seen_files.values()))

    # Step 5: Intelligent reranking
    should_rerank = _should_apply_reranker(plan, combined, rrf_scores, question)
    if should_rerank:
        _pipeline_stats["reranker_calls"] += 1
        # Rerank uses raw_content (which contains late-chunking context) for better precision
        combined = _rerank(query=question, docs=combined)

    # Step 6: HyDE fallback (if confidence is too low)
    max_rrf = max(rrf_scores.values()) if rrf_scores else 0.0
    if _HYDE_ENABLED and (not combined or max_rrf < _HYDE_THRESHOLD):
        logger.info(f"HyDE fallback activated (max score {max_rrf:.4f})")
        try:
            from src.retrieval.hyde import hyde_search
            hyde_docs = await hyde_search(question, None, store._embeddings, store, top_k=FINAL_TOP_N)
            combined = [{
                "id": d.metadata.get("chunk_id", d.page_content[:80]),
                "text": d.metadata.get("original_text", d.page_content),
                "filename": d.metadata.get("filename") or d.metadata.get("fichier", "unknown"),
                "indexed_at": float(d.metadata.get("indexed_at", 0.0) or 0.0)
            } for d in hyde_docs]
            rrf_scores = {d["id"]: 0.5 for d in combined}
        except Exception as e:
            logger.warning(f"HyDE fallback failed: {e}")

    # Finalize results
    combined = combined[:FINAL_TOP_N]
    passages = [d["text"] for d in combined]
    sources = [d.get("filename", "unknown") for d in combined]
    
    # Normalize scores for the UI
    max_score = max((rrf_scores.get(d["id"], 0.0) for d in combined), default=1.0) or 1.0
    conf_scores = [round(rrf_scores.get(d["id"], 0.0) / max_score, 3) for d in combined]

    _pipeline_stats.update(
        last_query=question[:80],
        last_mode="complex" if plan.is_complex else "simple",
        last_vector_count=len(vector_results),
        last_bm25_count=len(bm25_results)
    )
    
    return passages, sources, conf_scores, tie_subjects
