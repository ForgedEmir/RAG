"""Semantic cache for LLM responses.
Uses shared FastEmbed from vector_store (zero PyTorch, no second model load).
Stores embedding + response in Redis.

Multi-tenant isolation:
- Each tenant has its own Redis keyspace: scache:{tenant_id}:emb:{key}, scache:{tenant_id}:resp:{key}
- Each tenant has its own in-process matrix (rebuilt lazily on first access)
- Cross-tenant cache hits are impossible by construction
- Counter is per-tenant: scache:{tenant_id}:meta:count (each tenant capped at _MAX_ENTRIES)

Performance: local in-process normalized matrix for O(1) Redis round-trips on lookup.
- check(): 1 SCAN + 1 MGET to build matrix (lazy, cached per tenant), then 1 numpy dot-product.
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
# Rebuild local matrix after this many seconds (handles Redis TTL expiry drift)
_MATRIX_REFRESH_INTERVAL = int(os.getenv("SCACHE_MATRIX_REFRESH", "120"))

_redis      = None
_redis_lock = asyncio.Lock()

# ── In-process embedding matrices (per-tenant) ──────────────────────────────
# Pre-normalized rows → cosine similarity = simple dot product (no division needed).
# Keys are tenant_id → (matrix, emb_keys, ts, valid)
# A lock per-tenant avoids concurrent rebuilds for the same tenant.
_matrices:          dict                       = {}  # tenant_id -> np.ndarray
_matrix_keys:       dict                       = {}  # tenant_id -> List[str] (full Redis keys)
_matrix_ts:         dict                       = {}  # tenant_id -> float
_matrix_valid:      dict                       = {}  # tenant_id -> bool
_matrix_locks:      dict                       = {}  # tenant_id -> asyncio.Lock
_matrix_global_lock = asyncio.Lock()
_cache_initialized: bool                       = False


def _tenant_key_prefix(tenant_id: str) -> str:
    """Redis key prefix for a given tenant.
    The default tenant (empty string) uses the legacy prefix for backward compat."""
    if not tenant_id:
        return f"{_PREFIX}emb:"
    return f"{_PREFIX}{tenant_id}:emb:"


def _tenant_resp_prefix(tenant_id: str) -> str:
    if not tenant_id:
        return f"{_PREFIX}resp:"
    return f"{_PREFIX}{tenant_id}:resp:"


def _tenant_count_key(tenant_id: str) -> str:
    if not tenant_id:
        return f"{_PREFIX}meta:count"
    return f"{_PREFIX}{tenant_id}:meta:count"


async def _get_matrix_lock(tenant_id: str) -> asyncio.Lock:
    """Get or create the asyncio.Lock for a tenant's matrix."""
    if tenant_id in _matrix_locks:
        return _matrix_locks[tenant_id]
    async with _matrix_global_lock:
        if tenant_id not in _matrix_locks:
            _matrix_locks[tenant_id] = asyncio.Lock()
        return _matrix_locks[tenant_id]


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
                f"Semantic cache: dimension changed ({stored_dim}→{current_dim}). Clearing all tenants."
            )
            await clear_all()
        await r.set(version_key, str(current_dim))
    except Exception as e:
        logger.warning(f"Semantic cache version check failed: {e}")


# ── Matrix build (per-tenant) ────────────────────────────────────────────────

async def _build_matrix(tenant_id: str) -> Tuple[Optional[np.ndarray], List[str]]:
    """Load all cached embeddings for ONE tenant from Redis in two round-trips.
    Returns (normalized_matrix, list_of_emb_keys) or (None, []).
    """
    r = await _get_redis()
    if not r:
        return None, []

    emb_prefix = _tenant_key_prefix(tenant_id)

    # Round-trip 1: collect all emb keys for this tenant
    keys: List[str] = []
    cursor = 0
    while True:
        cursor, batch = await r.scan(cursor, match=f"{emb_prefix}*", count=500)
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

    logger.debug(f"Semantic cache matrix built for tenant={tenant_id or 'default'}: {len(valid_keys)} entries.")
    return matrix, valid_keys


async def _get_matrix(tenant_id: str) -> Tuple[Optional[np.ndarray], List[str]]:
    """Return the current (or refreshed) in-process matrix for a tenant. Thread-safe."""
    now = time.time()
    if _matrix_valid.get(tenant_id) and (now - _matrix_ts.get(tenant_id, 0.0)) < _MATRIX_REFRESH_INTERVAL:
        return _matrices.get(tenant_id), _matrix_keys.get(tenant_id, [])

    lock = await _get_matrix_lock(tenant_id)
    async with lock:
        # Double-check after acquiring the lock
        now = time.time()
        if _matrix_valid.get(tenant_id) and (now - _matrix_ts.get(tenant_id, 0.0)) < _MATRIX_REFRESH_INTERVAL:
            return _matrices.get(tenant_id), _matrix_keys.get(tenant_id, [])

        matrix, keys = await _build_matrix(tenant_id)
        _matrices[tenant_id]     = matrix
        _matrix_keys[tenant_id]  = keys
        _matrix_ts[tenant_id]    = now
        _matrix_valid[tenant_id] = True
        return matrix, keys


async def _invalidate_matrix(tenant_id: Optional[str] = None) -> None:
    """Invalidate matrix for one tenant (if specified) or all tenants (if None)."""
    if tenant_id is not None:
        lock = await _get_matrix_lock(tenant_id)
        async with lock:
            _matrix_valid[tenant_id] = False
    else:
        async with _matrix_global_lock:
            for tid in list(_matrix_valid.keys()):
                _matrix_valid[tid] = False


# ── Public API ────────────────────────────────────────────────────────────────

async def check(query: str, tenant_id: str = ""):
    """Search for a semantically similar cached response WITHIN one tenant.

    Args:
        query:     Question asked.
        tenant_id: Tenant scope. Empty string = default/global tenant.
                   A cache entry stored by tenant B can NEVER be served to tenant A.

    Returns (response_dict, score) or None.
    """
    await _ensure_cache_version()
    try:
        r = await _get_redis()
        if not r:
            return None

        q_vec = _embed(query)
        if q_vec is None:
            return None

        matrix, keys = await _get_matrix(tenant_id)
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
            # Build the matching resp_key by replacing the emb: prefix with resp:
            emb_prefix = _tenant_key_prefix(tenant_id)
            resp_prefix = _tenant_resp_prefix(tenant_id)
            resp_key = emb_key.replace(emb_prefix, resp_prefix, 1)
            raw_resp = await r.get(resp_key)
            if raw_resp:
                logger.info(f"Semantic cache HIT (tenant={tenant_id or 'default'}, sim={best_score:.3f})")
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


async def store(query: str, response: str, tenant_id: str = "",
                source_files: Optional[Iterable[str]] = None,
                context_chunks: Optional[List[dict]] = None) -> bool:
    """Store embedding + response metadata in Redis, scoped to a tenant.

    Uses a pipeline (1 round-trip) + INCR counter (per-tenant).

    Args:
        query:          Question asked.
        response:       Generated LLM response.
        tenant_id:      Tenant scope. Empty string = default/global tenant.
        source_files:   Source file names used to generate the response.
        context_chunks: Exact context chunks with their sources.
    """
    await _ensure_cache_version()
    try:
        r = await _get_redis()
        if not r:
            return False

        count_key = _tenant_count_key(tenant_id)
        # Use Redis counter — cheaper than SCAN+count
        count_raw = await r.get(count_key)
        count = int(count_raw or 0)
        if count >= _MAX_ENTRIES:
            logger.warning(f"Semantic cache full for tenant={tenant_id or 'default'} ({_MAX_ENTRIES}). Skipping.")
            return False

        vec = _embed(query)
        if vec is None:
            return False

        key      = hashlib.sha256(query.lower().encode()).hexdigest()[:16]
        emb_prefix = _tenant_key_prefix(tenant_id)
        resp_prefix = _tenant_resp_prefix(tenant_id)

        emb_json = json.dumps({
            "embedding":    vec,
            "query":        query,
            "source_files": sorted(set(source_files)) if source_files else [],
            "tenant_id":    tenant_id,  # Stored for auditability; the keyspace is the real isolation.
        })

        resp_json = json.dumps({
            "answer":         response,
            "sources":        sorted(set(s.split("/")[-1] for s in source_files)) if source_files else [],
            "context_chunks": context_chunks or [],
        })

        # Atomic pipeline — 1 round-trip
        pipe = r.pipeline()
        pipe.set(f"{emb_prefix}{key}",  emb_json,   ex=_TTL)
        pipe.set(f"{resp_prefix}{key}", resp_json,  ex=_TTL)
        pipe.incr(count_key)
        pipe.expire(count_key, _TTL)
        await pipe.execute()

        # Invalidate local matrix for this tenant so next check picks up the new entry
        await _invalidate_matrix(tenant_id)

        logger.info(f"Semantic cache STORE tenant={tenant_id or 'default'} key={key}")
        return True
    except Exception as e:
        logger.warning(f"Semantic cache store failed: {e}")
        return False


async def clear_all(tenant_id: Optional[str] = None) -> None:
    """Clear semantic cache entries.

    Args:
        tenant_id: If specified, clear ONLY this tenant's entries.
                   If None, clear ALL tenants (used for dimension changes, full resets).
    """
    try:
        r = await _get_redis()
        if not r:
            return

        if tenant_id is not None:
            # Per-tenant clear: only delete this tenant's emb/resp/count keys
            emb_prefix = _tenant_key_prefix(tenant_id)
            resp_prefix = _tenant_resp_prefix(tenant_id)
            count_key = _tenant_count_key(tenant_id)
            for prefix in (emb_prefix, resp_prefix):
                cursor = 0
                while True:
                    cursor, keys = await r.scan(cursor, match=f"{prefix}*", count=500)
                    if keys:
                        await r.delete(*keys)
                    if cursor == 0:
                        break
            try:
                await r.delete(count_key)
            except Exception:
                pass
            await _invalidate_matrix(tenant_id)
            logger.info(f"Semantic cache cleared for tenant={tenant_id or 'default'}.")
        else:
            # Global clear (all tenants)
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=f"{_PREFIX}*", count=500)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break
            await _invalidate_matrix(None)
            logger.info("Semantic cache cleared (all tenants).")
    except Exception as e:
        logger.warning(f"Semantic cache clear failed: {e}")


async def invalidate_for_files(filenames: Iterable[str], tenant_id: str = "") -> int:
    """Invalidates entries (within one tenant) whose source_files intersect with ``filenames``.

    WHY: After a re-index (file modified/added/deleted), the cached LLM responses
    that relied on this file are potentially outdated.
    We only purge these entries to keep the cache warm for the others.

    Args:
        filenames: Files that changed.
        tenant_id: Tenant scope. Empty string = default/global tenant.

    Returns: number of entries (emb/resp pairs) deleted.
    """
    targets = {f for f in filenames if f}
    if not targets:
        return 0

    try:
        r = await _get_redis()
        if not r:
            return 0

        emb_prefix = _tenant_key_prefix(tenant_id)
        resp_prefix = _tenant_resp_prefix(tenant_id)
        count_key = _tenant_count_key(tenant_id)

        to_delete: List[str] = []
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor, match=f"{emb_prefix}*", count=500)
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
                    # Legacy entry (pre-tracking). Fail-safe: invalidate.
                    should_delete = True
                else:
                    sources = set(parsed.get("source_files") or [])
                    should_delete = bool(sources & targets)

                if should_delete:
                    resp_key = key.replace(emb_prefix, resp_prefix, 1)
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
            # Keep the per-tenant counter in sync.
            try:
                await r.decrby(count_key, removed_pairs)
                count_raw = await r.get(count_key)
                current = int(count_raw or 0)
                if current < 0:
                    await r.set(count_key, 0, ex=_TTL)
            except Exception:
                pass
            await _invalidate_matrix(tenant_id)
            logger.info(
                f"Semantic cache (tenant={tenant_id or 'default'}): "
                f"{removed_pairs} entry/entries invalidated for {sorted(targets)}."
            )
        return removed_pairs
    except Exception as e:
        logger.warning(f"Semantic cache invalidation failed: {e}")
        return 0


async def stats(tenant_id: Optional[str] = None) -> dict:
    """Return cache stats.

    Args:
        tenant_id: If specified, return stats for this tenant only.
                   If None, return aggregate stats across all tenants.
    """
    try:
        r = await _get_redis()
        if not r:
            return {"status": "redis_unavailable", "entries": 0}

        if tenant_id is not None:
            count_key = _tenant_count_key(tenant_id)
            count_raw = await r.get(count_key)
            count = int(count_raw or 0)
            async with _matrix_global_lock:
                matrix_size  = len(_matrix_keys.get(tenant_id, [])) if _matrix_valid.get(tenant_id) else None
                matrix_age_s = round(time.time() - _matrix_ts.get(tenant_id, 0.0)) if _matrix_ts.get(tenant_id) else None
            return {
                "status":       "ok",
                "tenant_id":    tenant_id or "default",
                "entries":      count,
                "max":          _MAX_ENTRIES,
                "threshold":    _THRESHOLD,
                "ttl":          _TTL,
                "matrix_size":  matrix_size,
                "matrix_age_s": matrix_age_s,
            }
        # Aggregate stats across all tenants
        cursor = 0
        total = 0
        tenant_counts: dict = {}
        while True:
            cursor, keys = await r.scan(cursor, match=f"{_PREFIX}*meta:count", count=500)
            for k in keys:
                v = await r.get(k)
                c = int(v or 0)
                total += c
                # Extract tenant_id from key: scache:{tenant_id}:meta:count or scache:meta:count
                if k == f"{_PREFIX}meta:count":
                    tenant_counts["default"] = c
                else:
                    tid = k[len(_PREFIX):-len(":meta:count")]
                    tenant_counts[tid] = c
            if cursor == 0:
                break
        return {
            "status":        "ok",
            "entries":       total,
            "max_per_tenant": _MAX_ENTRIES,
            "threshold":     _THRESHOLD,
            "ttl":           _TTL,
            "tenants":       tenant_counts,
        }
    except Exception:
        return {"status": "error", "entries": 0}
