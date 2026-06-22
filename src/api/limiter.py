import os
import logging
import json
import hashlib
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

DEFAULT_STORAGE = "memory://"
REDIS_TIMEOUT = 1
APP_ENV = os.getenv("APP_ENV", "development").lower()
ALLOW_GUEST_MODE = os.getenv("ALLOW_GUEST_MODE", "false").lower() == "true"
ALLOW_LOCAL_GUEST_HEADER = os.getenv("ALLOW_LOCAL_GUEST_HEADER", "true").lower() == "true"

def _get_key(request: Request) -> str:
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
            return f"jwt:{token_hash}"

    try:
        # Use session_id for granularity if the body was already cached by a middleware
        body = request.state.__dict__.get("_body")
        if body:
            data = json.loads(body)
            if session_id := data.get("session_id", "").strip():
                return session_id
    except Exception:
        pass

    # The guest header is easily spoofable; we only use it in local guest mode.
    guest_allowed = ALLOW_GUEST_MODE and ALLOW_LOCAL_GUEST_HEADER and APP_ENV != "production"
    if guest_allowed:
        guest_id = (request.headers.get("x-local-guest-id") or "").strip()
        if guest_id.startswith("guest_"):
            return f"guest:{guest_id}"

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

async def rate_limit_handler(request: Request, exc: Exception) -> JSONResponse:
    # WHY: this handler is now async so we can `await` the async track() call.
    # Previously, track() (async) was called without await → coroutine was
    # garbage-collected → rate-limit events were silently lost from tracking.
    from src.monitoring.tracker import track
    try:
        await track("rate_limit", detail=request.client.host if request.client else "unknown")
    except Exception:
        pass
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Please wait.", "blocked": True, "block_type": "rate_limit"},
    )
