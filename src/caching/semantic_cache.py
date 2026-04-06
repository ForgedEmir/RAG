"""Semantic cache for LLM responses.
Semantic cache for LLM responses. Uses shared FastEmbed from vector_store (zero PyTorch, no second model load).
Store embedding as JSON string in Redis (compatible with decode_responses=True).
"""
import hashlib
import json
import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

import os
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_THRESHOLD = 0.92
_TTL = 3600
_MAX_ENTRIES = 5000
_PREFIX = "scache:"

_redis = None
_cache_initialized = False


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis
        _redis = redis.Redis.from_url(
            _REDIS_URL, decode_responses=True,
            socket_connect_timeout=5, socket_timeout=5,
        )
        _redis.ping()
        return _redis
    except Exception as e:
        logger.warning(f"Semantic cache Redis unavailable: {e}")
        return None


def _embed(text):
    """Use the shared embedder from vector_store to avoid loading a second model."""
    try:
        from src.ingestion.vector_store import _get_embeddings
        emb = _get_embeddings()
        return emb.embed_query(text)
    except Exception:
        return None


def _ensure_cache_version():
    """Vide le cache Redis si la dimension du modèle a changé."""
    global _cache_initialized
    if _cache_initialized:
        return
    _cache_initialized = True
    try:
        r = _get_redis()
        if not r:
            return
        from src.ingestion.vector_store import _get_vector_size
        current_dim = _get_vector_size()
        version_key = f"{_PREFIX}meta:dim"
        stored_dim = r.get(version_key)
        if stored_dim is not None and int(stored_dim) != current_dim:
            logger.warning(
                f"Semantic cache : dimension changée ({stored_dim}→{current_dim}). Vidage du cache."
            )
            clear_all()
        r.set(version_key, str(current_dim))
    except Exception as e:
        logger.warning(f"Semantic cache version check failed: {e}")


def check(query):
    """Search Redis for similar cached responses. Returns (response, score) or None."""
    _ensure_cache_version()
    try:
        r = _get_redis()
        if not r:
            return None
        q_vec = _embed(query)
        if q_vec is None:
            return None
        q_arr = np.array(q_vec, dtype=np.float32)

        best_score, best_resp = 0.0, None
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{_PREFIX}emb:*", count=200)
            for key in keys:
                try:
                    emb_json = r.get(key)
                    if not emb_json:
                        continue
                    cached = json.loads(emb_json)
                    cached_emb = np.array(cached["embedding"], dtype=np.float32)
                    sim = float(
                        np.dot(q_arr, cached_emb)
                        / (max(np.linalg.norm(q_arr), 1e-9) * max(np.linalg.norm(cached_emb), 1e-9))
                    )
                    if sim > best_score:
                        best_score = sim
                        resp_key = key.replace(f"{_PREFIX}emb:", f"{_PREFIX}resp:")
                        best_resp = r.get(resp_key)
                except Exception:
                    pass
            if cursor == 0:
                break

        if best_score >= _THRESHOLD and best_resp:
            logger.info(f"Semantic cache HIT (sim={best_score:.3f})")
            return best_resp, round(best_score, 4)
    except Exception as e:
        logger.warning(f"Semantic cache check failed: {e}")
    return None


def store(query, response):
    """Store embedding + response in Redis as JSON strings."""
    _ensure_cache_version()
    try:
        r = _get_redis()
        if not r:
            return False
        if len(r.keys(f"{_PREFIX}emb:*")) >= _MAX_ENTRIES:
            logger.warning("Semantic cache full (5000). Skipping.")
            return False
        vec = _embed(query)
        if vec is None:
            return False
        key = hashlib.sha256(query.lower().encode()).hexdigest()[:16]
        emb_json = json.dumps({"embedding": vec, "query": query})
        r.set(f"{_PREFIX}emb:{key}", emb_json, ex=_TTL)
        r.set(f"{_PREFIX}resp:{key}", response, ex=_TTL)
        logger.info(f"Semantic cache STORE key={key}")
        return True
    except Exception as e:
        logger.warning(f"Semantic cache store failed: {e}")
        return False


def clear_all():
    """Clear all semantic cache entries from Redis."""
    try:
        r = _get_redis()
        if not r:
            return
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{_PREFIX}*", count=500)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning(f"Semantic cache clear failed: {e}")


def stats():
    try:
        r = _get_redis()
        if not r:
            return {"status": "redis_unavailable", "entries": 0}
        n = 0
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{_PREFIX}emb:*", count=200)
            n += len(keys)
            if cursor == 0:
                break
        return {"status": "ok", "entries": n, "max": _MAX_ENTRIES, "threshold": _THRESHOLD, "ttl": _TTL}
    except Exception:
        return {"status": "error", "entries": 0}
