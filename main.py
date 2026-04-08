"""Oracle LoreKeeper — Point d'entrée FastAPI."""
import os
import logging
import threading
import subprocess
import warnings
from collections import deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(override=False)
_is_dev = os.getenv("ENV", "production").lower() == "development"

# Sentry (optionnel)
if dsn := os.getenv("SENTRY_DSN"):
    import sentry_sdk
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.2)

# ── Buffer de logs en mémoire ─────────────────────────────────────────
_LOG_BUFFER_SIZE = max(100, int(os.getenv("LOG_BUFFER_SIZE", "1000")))
_log_buffer: deque = deque(maxlen=_LOG_BUFFER_SIZE)

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
logger = logging.getLogger(__name__)
# Capture warnings.warn(...) into the standard logging pipeline.
logging.captureWarnings(True)
warnings.simplefilter("default")
warnings.filterwarnings(
    "ignore",
    message=r".*BaseCommand.*deprecated.*Click 9.0.*",
    category=DeprecationWarning,
    module=r"typer\.completion",
)
warnings.filterwarnings(
    "ignore",
    message=r".*parser\.split_arg_string.*deprecated.*Click 9.0.*",
    category=DeprecationWarning,
    module=r"spacy\.cli\._util",
)
warnings.filterwarnings(
    "ignore",
    message=r".*parser\.split_arg_string.*deprecated.*Click 9.0.*",
    category=DeprecationWarning,
    module=r"weasel\.util\.config",
)

def _attach_buffer_handler_to_logger(logger_name: str) -> None:
    lg = logging.getLogger(logger_name)
    if not any(h is _buf_handler for h in lg.handlers):
        lg.addHandler(_buf_handler)

# Include web server logs in /api/monitoring/logs when available.
for _name in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn", "gunicorn.error", "gunicorn.access", "py.warnings"):
    _attach_buffer_handler_to_logger(_name)

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


_LOCK_FILE = os.path.join(os.path.dirname(__file__), ".startup.lock")

def _is_first_worker() -> bool:
    """Utilise un fichier lock pour qu'un seul worker Gunicorn lance l'indexation."""
    try:
        fd = os.open(_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False

def _warmup() -> None:
    """Pré-charge FastEmbed + Reranker ONNX en parallèle pour éliminer la latence sur la première requête."""
    import time

    def _load_embeddings():
        t = time.monotonic()
        try:
            from src.ingestion.vector_store import _get_embeddings
            _get_embeddings()
            logger.info(f"[WARMUP] FastEmbed prêt ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] FastEmbed échoué : {e}")

    def _load_reranker():
        t = time.monotonic()
        try:
            from src.search.search import _get_reranker
            _get_reranker()
            logger.info(f"[WARMUP] Reranker prêt ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] Reranker échoué : {e}")

    t0 = time.monotonic()
    t_embed = threading.Thread(target=_load_embeddings, daemon=True)
    t_rerank = threading.Thread(target=_load_reranker, daemon=True)
    t_embed.start()
    t_rerank.start()
    t_embed.join()
    t_rerank.join()
    logger.info(f"[WARMUP] Terminé ({time.monotonic() - t0:.1f}s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    first = _is_first_worker()
    if first:
        # Indexation initiale en arrière-plan → le serveur répond aux health checks immédiatement
        threading.Thread(target=index_data, kwargs={"force_reindex": False}, daemon=True).start()
        # Pré-charge FastEmbed + Reranker ONNX pour que la première requête ne paie pas le coût de chargement
        threading.Thread(target=_warmup, daemon=True).start()
        # Watchdog sur data/sample/ pour réindexer automatiquement si un fichier change
        start_watchdog()
    yield
    if first:
        stop_watchdog()
        try:
            os.remove(_LOCK_FILE)
        except OSError:
            pass


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
_root_dir = os.path.dirname(__file__)
_frontend_react_dir = os.path.join(_root_dir, "src", "frontend-react")
_frontend_react_dist = os.path.join(_frontend_react_dir, "dist")


def _ensure_frontend_build() -> None:
    """Build React frontend locally if no static frontend is available."""
    if _is_dev:
        return

    index_file = os.path.join(_frontend_react_dist, "index.html")
    if os.path.isfile(index_file):
        return

    package_json = os.path.join(_frontend_react_dir, "package.json")
    if not os.path.isfile(package_json):
        return

    logger.info("Frontend non buildé: tentative de build automatique (npm run build)")
    npm_commands = [
        ["npm", "run", "build"],
        ["npm.cmd", "run", "build"],
        ["cmd", "/c", "npm", "run", "build"],
    ]
    last_error = ""

    for cmd in npm_commands:
        try:
            result = subprocess.run(
                cmd,
                cwd=_frontend_react_dir,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                return
            stderr_tail = (result.stderr or "").strip()[-500:]
            last_error = f"code={result.returncode} {stderr_tail}".strip()
        except FileNotFoundError:
            continue
        except Exception as e:
            last_error = str(e)

    logger.warning(
        "Build frontend automatique impossible. Installez Node.js/npm ou lancez manuellement: "
        "cd src/frontend-react && npm install && npm run build"
        + (f" | Détail: {last_error}" if last_error else "")
    )


_ensure_frontend_build()

_frontend_candidates = [
    os.path.join(_root_dir, "frontend"),
    os.path.join(_root_dir, "src", "frontend"),
    _frontend_react_dist,
]

_frontend = _frontend_candidates[0]
for candidate in _frontend_candidates:
    if os.path.isdir(candidate):
        _frontend = candidate
        break

_assets_dir = os.path.join(_frontend, "assets")
_index_file = os.path.join(_frontend, "index.html")

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if _is_dev and (path.startswith("/assets/") or path.endswith(".html") or path == "/"):
            # Dev uniquement : désactive le cache pour voir les changements immédiatement
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif path.startswith("/assets/"):
            # Prod : évite les assets obsolètes derrière certains reverse proxies/CDN.
            # On pourra assouplir plus tard quand le déploiement sera stabilisé.
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif path.endswith(".html") or path == "/":
            # Prod : HTML non mis en cache (pour détecter les nouvelles versions)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheStaticMiddleware)

# Assets statiques montés sur /assets/ (JS, CSS, images)
if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")
else:
    logger.warning(f"Frontend assets introuvables: {_assets_dir}. '/assets' non monté.")

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
    if os.path.isfile(_index_file):
        return _FileResponse(_index_file)
    return JSONResponse(
        {
            "error": "Frontend non buildé",
            "detail": "Lancez le build frontend (npm run build) ou démarrez en Docker.",
        },
        status_code=503,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=_is_dev)
