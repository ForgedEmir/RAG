"""Oracle LoreKeeper — Point d'entrée FastAPI."""
import os
import logging
import threading
from collections import deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(override=False)

# Sentry (optionnel)
if dsn := os.getenv("SENTRY_DSN"):
    import sentry_sdk
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.2)

# ── Buffer de logs en mémoire (200 dernières lignes) ─────────────────────────
_log_buffer: deque = deque(maxlen=200)

class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _log_buffer.append({
            "time":  self.formatter.formatTime(record, "%H:%M:%S"),
            "level": record.levelname,
            "name":  record.name,
            "msg":   record.getMessage(),
        })

_buf_handler = _BufferHandler()
_buf_handler.setFormatter(logging.Formatter())
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
logging.getLogger().addHandler(_buf_handler)
# Silencer les logs HTTP externes (Supabase, Qdrant, OpenRouter) — trop verbeux en prod
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

# ── App FastAPI ───────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from src.api.limiter import limiter, rate_limit_handler
from src.api.routes import register_routes
from src.ingestion.run import index_data
from src.ingestion.watcher import start_watchdog, stop_watchdog


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Indexation initiale en arrière-plan → le serveur répond aux health checks immédiatement
    threading.Thread(target=index_data, kwargs={"force_reindex": False}, daemon=True).start()
    # Watchdog sur data/sample/ pour réindexer automatiquement si un fichier change
    start_watchdog()
    yield
    stop_watchdog()


app = FastAPI(title="Oracle LoreKeeper", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

_allowed_origins = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080"
).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app, _log_buffer)

# Fichiers statiques (frontend) — no-cache en dev pour éviter les versions périmées
_frontend = os.path.join(os.path.dirname(__file__), "src", "frontend")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

_is_dev = os.getenv("ENV", "production").lower() == "development"

class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if _is_dev and (path.startswith("/assets/") or path.endswith(".html") or path == "/"):
            # Dev uniquement : désactive le cache pour voir les changements immédiatement
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif path.endswith(".html") or path == "/":
            # Prod : HTML non mis en cache (pour détecter les nouvelles versions)
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

app.add_middleware(NoCacheStaticMiddleware)

# Assets statiques montés sur /assets/ (JS, CSS, images)
app.mount("/assets", StaticFiles(directory=os.path.join(_frontend, "assets")), name="assets")

# Catch-all SPA : sert index.html pour /chat, /monitoring, etc.
# Doit être APRÈS les routes API et APRÈS /assets
from fastapi.responses import FileResponse as _FileResponse

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Servir les fichiers statiques à la racine (favicon.svg, icons.svg…)
    static_file = os.path.join(_frontend, full_path)
    if full_path and os.path.isfile(static_file):
        return _FileResponse(static_file)
    # Toutes les autres routes → index.html (React Router gère côté client)
    return _FileResponse(os.path.join(_frontend, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=_is_dev)
