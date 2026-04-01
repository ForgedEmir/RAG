"""Rate limiter SlowAPI (FastAPI). Redis si REDIS_URL défini, sinon mémoire locale."""
import os
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _get_key(request: Request) -> str:
    try:
        # Limite par session_id si dispo, sinon par IP
        body = request.state.__dict__.get("_body")
        if body:
            import json
            data = json.loads(body)
            if sid := data.get("session_id", "").strip():
                return sid
    except Exception:
        pass
    return get_remote_address(request)


def _resolve_storage_uri() -> str:
    """Utilise Redis si joignable, sinon fallback mémoire."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return "memory://"

    try:
        import redis
        client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        logger.info("Rate limit storage: Redis")
        return redis_url
    except Exception as exc:
        logger.warning(f"Redis indisponible pour rate limiting, fallback mémoire: {exc}")
        return "memory://"


limiter = Limiter(
    key_func=_get_key,
    storage_uri=_resolve_storage_uri(),
)


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
