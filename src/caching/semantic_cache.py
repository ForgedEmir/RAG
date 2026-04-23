"""Semantic cache for LLM responses.
Uses shared FastEmbed from vector_store (zero PyTorch, no second model load).
Stores embedding + response in Redis.

Performance: local in-process normalized matrix for O(1) Redis round-trips on lookup.
- check(): 1 SCAN + 1 MGET to build matrix (lazy, cached), then 1 numpy dot-product.
- store(): pipeline (SET emb + SET resp + INCR counter) — 1 round-trip.
"""
import hashlib
import json
import logging
import os
import asyncio
import time
from typing import Iterable, List, Optional, Tuple

import numpy as np
from redis import asyncio as aioredis

logger = logging.getLogger(__name__)

_REDIS_URL   = os.getenv("REDIS_URL", "redis://localhost:6379")
_THRESHOLD   = 0.92
_TTL         = 3600
_MAX_ENTRIES = 5000
_PREFIX      = "scache:"
_COUNT_KEY   = f"{_PREFIX}meta:count"
# Rebuild local matrix after this many seconds (handles Redis TTL expiry drift)
_MATRIX_REFRESH_INTERVAL = int(os.getenv("SCACHE_MATRIX_REFRESH", "120"))

_redis      = None
_redis_lock = asyncio.Lock()

# ── In-process embedding matrix ───────────────────────────────────────────────
# Pre-normalized rows → cosine similarity = simple dot product (no division needed).
_matrix:       Optional[np.ndarray] = None  # shape (n, dim), float32, L2-normalized
_matrix_keys:  List[str]            = []    # emb key for each row (includes _PREFIX)
_matrix_ts:    float                = 0.0   # unix timestamp of last build
_matrix_valid: bool                 = False
_matrix_lock                        = asyncio.Lock()
_cache_initialized: bool            = False


# ── Redis ─────────────────────────────────────────────────────────────────────

async def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    async with _redis_lock:
        if _redis is None:
            try:
                _redis = aioredis.Redis.from_url(
                    _REDIS_URL, decode_responses=True,
                    socket_connect_timeout=5, socket_timeout=5,
                )
                await _redis.ping()
            except Exception as e:
                logger.warning(f"Semantic cache Redis unavailable: {e}")
                _redis = None
    return _redis


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(text: str) -> Optional[List[float]]:
    """Shared embedder from vector_store — no second model load."""
    try:
        from src.ingestion.vector_store import _get_embeddings
        return _get_embeddings().embed_query(text)
    except Exception:
        return None


# ── Cache version (dim check) ─────────────────────────────────────────────────

async def _ensure_cache_version() -> None:
    global _cache_initialized
    if _cache_initialized:
        return
    _cache_initialized = True
    try:
        r = await _get_redis()
        if not r:
            return
        from src.ingestion.vector_store import _get_vector_size
        current_dim = _get_vector_size()
        version_key = f"{_PREFIX}meta:dim"
        stored_dim  = await r.get(version_key)
        if stored_dim is not None and int(stored_dim) != current_dim:
            logger.warning(
                f"Semantic cache: dimension changed ({stored_dim}→{current_dim}). Clearing."
            )
            await clear_all()
        await r.set(version_key, str(current_dim))
    except Exception as e:
        logger.warning(f"Semantic cache version check failed: {e}")


# ── Matrix build ──────────────────────────────────────────────────────────────

async def _build_matrix() -> Tuple[Optional[np.ndarray], List[str]]:
    """Load all cached embeddings from Redis in two round-trips (SCAN + MGET).
    Returns (normalized_matrix, list_of_emb_keys) or (None, []).
    """
    r = await _get_redis()
    if not r:
        return None, []

    # Round-trip 1: collect all emb keys
    keys: List[str] = []
    cursor = 0
    while True:
        cursor, batch = await r.scan(cursor, match=f"{_PREFIX}emb:*", count=500)
        keys.extend(batch)
        if cursor == 0:
            break

    if not keys:
        return None, []

    # Round-trip 2: fetch all embeddings in one MGET
    raw_values = await r.mget(keys)

    embeddings, valid_keys = [], []
    expected_dim: Optional[int] = None
    for key, raw in zip(keys, raw_values):
        if not raw:
            continue
        try:
            emb = json.loads(raw)["embedding"]
            if not isinstance(emb, list) or not emb:
                continue
            # Ignore entries from a previous embedding model (different dimension)
            if expected_dim is None:
                expected_dim = len(emb)
            if len(emb) != expected_dim:
                continue
            embeddings.append(emb)
            valid_keys.append(key)
        except Exception:
            pass

    if not embeddings:
        return None, []

    matrix = np.array(embeddings, dtype=np.float32)
    # Pre-normalize rows → cosine sim = dot product at query time
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-9)
    matrix /= norms

    logger.debug(f"Semantic cache matrix built: {len(valid_keys)} entries.")
    return matrix, valid_keys


async def _get_matrix() -> Tuple[Optional[np.ndarray], List[str]]:
    """Return the current (or refreshed) in-process matrix. Thread-safe."""
    global _matrix, _matrix_keys, _matrix_ts, _matrix_valid
    async with _matrix_lock:
        now = time.time()
        if _matrix_valid and (now - _matrix_ts) < _MATRIX_REFRESH_INTERVAL:
            return _matrix, _matrix_keys
        _matrix, _matrix_keys = await _build_matrix()
        _matrix_ts    = now
        _matrix_valid = True
        return _matrix, _matrix_keys


async def _invalidate_matrix() -> None:
    global _matrix_valid
    async with _matrix_lock:
        _matrix_valid = False


# ── Public API ────────────────────────────────────────────────────────────────

async def check(query: str):
    """Search for a semantically similar cached response.
    Returns (response_dict, score) or None.

    Complexity: O(n) numpy dot-product (vectorized) — no Redis loop.
    """
    await _ensure_cache_version()
    try:
        r = await _get_redis()
        if not r:
            return None

        q_vec = _embed(query)
        if q_vec is None:
            return None

        matrix, keys = await _get_matrix()
        if matrix is None or len(keys) == 0:
            return None

        # Normalize query once
        q_arr  = np.array(q_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q_arr))
        if q_norm < 1e-9:
            return None
        q_arr /= q_norm

        # Single vectorized cosine similarity
        sims      = matrix @ q_arr          # shape (n,)
        best_idx  = int(np.argmax(sims))
        best_score = float(sims[best_idx])

        if best_score >= _THRESHOLD:
            emb_key  = keys[best_idx]
            resp_key = emb_key.replace(f"{_PREFIX}emb:", f"{_PREFIX}resp:")
            raw_resp = await r.get(resp_key)
            if raw_resp:
                logger.info(f"Semantic cache HIT (sim={best_score:.3f})")
                try:
                    data = json.loads(raw_resp)
                    if isinstance(data, dict) and "answer" in data:
                        return data, round(best_score, 4)
                    # Support legacy plain-text entries
                    return {"answer": raw_resp, "sources": [], "context_chunks": []}, round(best_score, 4)
                except json.JSONDecodeError:
                    return {"answer": raw_resp, "sources": [], "context_chunks": []}, round(best_score, 4)
    except Exception as e:
        logger.warning(f"Semantic cache check failed: {e}")
    return None


async def store(query: str, response: str, source_files: Optional[Iterable[str]] = None,
          context_chunks: Optional[List[dict]] = None) -> bool:
    """Store embedding + response metadata in Redis.
    Uses a pipeline (1 round-trip) + INCR counter.

    Args:
        query:          Question posée.
        response:       Réponse LLM générée.
        source_files:   Noms de fichiers sources ayant servi à générer la réponse.
        context_chunks: Passages de contexte exacts avec leurs sources.
    """
    await _ensure_cache_version()
    try:
        r = await _get_redis()
        if not r:
            return False

        # Use Redis counter — cheaper than SCAN+count
        count_raw = await r.get(_COUNT_KEY)
        count = int(count_raw or 0)
        if count >= _MAX_ENTRIES:
            logger.warning(f"Semantic cache full ({_MAX_ENTRIES}). Skipping.")
            return False

        vec = _embed(query)
        if vec is None:
            return False

        key      = hashlib.sha256(query.lower().encode()).hexdigest()[:16]
        emb_json = json.dumps({
            "embedding":    vec,
            "query":        query,
            "source_files": sorted(set(source_files)) if source_files else [],
        })
        
        resp_json = json.dumps({
            "answer":         response,
            "sources":        sorted(set(source_files)) if source_files else [],
            "context_chunks": context_chunks or [],
        })

        # Atomic pipeline — 1 round-trip
        pipe = r.pipeline()
        pipe.set(f"{_PREFIX}emb:{key}",  emb_json,   ex=_TTL)
        pipe.set(f"{_PREFIX}resp:{key}", resp_json,  ex=_TTL)
        pipe.incr(_COUNT_KEY)
        pipe.expire(_COUNT_KEY, _TTL)
        await pipe.execute()

        # Invalidate local matrix so next check picks up the new entry
        await _invalidate_matrix()

        logger.info(f"Semantic cache STORE key={key}")
        return True
    except Exception as e:
        logger.warning(f"Semantic cache store failed: {e}")
        return False


async def clear_all() -> None:
    """Clear all semantic cache entries from Redis and local matrix."""
    try:
        r = await _get_redis()
        if not r:
            return
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=f"{_PREFIX}*", count=500)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
        # Reset the counter too, otherwise store() will believe the cache is full.
        try:
            await r.delete(_COUNT_KEY)
        except Exception:
            pass
        await _invalidate_matrix()
    except Exception as e:
        logger.warning(f"Semantic cache clear failed: {e}")


async def invalidate_for_files(filenames: Iterable[str]) -> int:
    """Invalide les entrées dont les source_files croisent ``filenames``.

    WHY: Après un re-index (fichier modifié/ajouté/supprimé), les réponses LLM
    cachées qui s'appuyaient sur ce fichier sont potentiellement périmées.
    On ne purge que ces entrées pour conserver le cache chaud sur les autres.

    Les entrées antérieures à cette version (pas de clé ``source_files`` stockée)
    sont purgées par sécurité dès qu'un fichier change — on ne peut pas savoir
    d'où elles venaient.

    Returns: nombre d'entrées (paires emb/resp) supprimées.
    """
    targets = {f for f in filenames if f}
    if not targets:
        return 0

    try:
        r = await _get_redis()
        if not r:
            return 0

        to_delete: List[str] = []
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=f"{_PREFIX}emb:*", count=500)
            if not keys:
                if cursor == 0:
                    break
                continue

            raw_values = await r.mget(keys)
            for key, raw in zip(keys, raw_values):
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue

                if "source_files" not in parsed:
                    # Legacy entry (pre-tracking). Fail-safe : invalider.
                    should_delete = True
                else:
                    sources = set(parsed.get("source_files") or [])
                    should_delete = bool(sources & targets)

                if should_delete:
                    resp_key = key.replace(f"{_PREFIX}emb:", f"{_PREFIX}resp:")
                    to_delete.extend([key, resp_key])

            if cursor == 0:
                break

        removed_pairs = 0
        if to_delete:
            # Chunk deletions to avoid oversized Redis commands.
            batch = 500
            for i in range(0, len(to_delete), batch):
                await r.delete(*to_delete[i:i + batch])
            removed_pairs = len(to_delete) // 2
            # Keep the counter in sync with the actual number of cached entries.
            try:
                await r.decrby(_COUNT_KEY, removed_pairs)
                count_raw = await r.get(_COUNT_KEY)
                current = int(count_raw or 0)
                if current < 0:
                    await r.set(_COUNT_KEY, 0, ex=_TTL)
            except Exception:
                pass
            await _invalidate_matrix()
            logger.info(
                f"Semantic cache : {removed_pairs} entrée(s) invalidée(s) pour {sorted(targets)}."
            )
        return removed_pairs
    except Exception as e:
        logger.warning(f"Semantic cache invalidation failed: {e}")
        return 0


async def stats() -> dict:
    try:
        r = await _get_redis()
        if not r:
            return {"status": "redis_unavailable", "entries": 0}
        count_raw = await r.get(_COUNT_KEY)
        count = int(count_raw or 0)
        async with _matrix_lock:
            matrix_size  = len(_matrix_keys) if _matrix_valid else None
            matrix_age_s = round(time.time() - _matrix_ts) if _matrix_ts else None
        return {
            "status":       "ok",
            "entries":      count,
            "max":          _MAX_ENTRIES,
            "threshold":    _THRESHOLD,
            "ttl":          _TTL,
            "matrix_size":  matrix_size,
            "matrix_age_s": matrix_age_s,
        }
    except Exception:
        return {"status": "error", "entries": 0}
