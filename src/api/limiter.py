import os
import logging
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

DEFAULT_STORAGE = "memory://"
REDIS_TIMEOUT = 1

def _get_key(request: Request) -> str:
    try:
        # Use session_id for granularity if the body was already cached by a middleware
        body = request.state.__dict__.get("_body")
        if body:
            data = json.loads(body)
            if session_id := data.get("session_id", "").strip():
                return session_id
    except Exception:
        pass
    return get_remote_address(request)

def _resolve_storage_uri() -> str:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return DEFAULT_STORAGE
    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=REDIS_TIMEOUT, socket_timeout=REDIS_TIMEOUT)
        client.ping()
        logger.info("Rate limit storage: Redis")
        return redis_url
    except Exception as exc:
        logger.warning(f"Redis unavailable for rate limiting, falling back to memory: {exc}")
        return DEFAULT_STORAGE

limiter = Limiter(key_func=_get_key, storage_uri=_resolve_storage_uri())

def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    from src.monitoring.tracker import track
    try:
        track("rate_limit", detail=request.client.host if request.client else "unknown")
    except Exception:
        pass
    return JSONResponse(
        status_code=429,
        content={"error": "Trop de requêtes. Merci de patienter.", "blocked": True, "block_type": "rate_limit"},
    )
