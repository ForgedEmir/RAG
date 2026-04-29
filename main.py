"""Oracle LoreKeeper — FastAPI entry point."""
import os
import logging
import threading
import subprocess
import time
import warnings
from collections import deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(override=False)
from src.config.features import apply_feature_profile, env_bool

apply_feature_profile()
_is_dev = os.getenv("ENV", "production").lower() == "development"

# Sentry (optional)
if dsn := os.getenv("SENTRY_DSN"):
    import sentry_sdk
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.2)

# ── In-memory log buffer ──────────────────────────────────────────────
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
warnings.filterwarnings(
    "ignore",
    message=r".*'timeout' parameter is deprecated.*",
    category=DeprecationWarning,
    module=r"supabase\._sync\.client",
)
warnings.filterwarnings(
    "ignore",
    message=r".*'verify' parameter is deprecated.*",
    category=DeprecationWarning,
    module=r"supabase\._sync\.client",
)
warnings.filterwarnings(
    "ignore",
    message=r".*asyncio\.iscoroutinefunction.*deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*websockets\.legacy is deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r".*websockets\.server\.WebSocketServerProtocol is deprecated.*",
    category=DeprecationWarning,
)

def _attach_buffer_handler_to_logger(logger_name: str) -> None:
    lg = logging.getLogger(logger_name)
    if not any(h is _buf_handler for h in lg.handlers):
        lg.addHandler(_buf_handler)

# Include web server logs in /api/monitoring/logs when available.
# uvicorn.access excluded — it logs every HTTP request and pollutes the monitoring buffer.
for _name in ("uvicorn", "uvicorn.error", "gunicorn", "gunicorn.error", "gunicorn.access", "py.warnings"):
    _attach_buffer_handler_to_logger(_name)

# Silence verbose external HTTP logs (Supabase, Qdrant, OpenRouter)
logging.getLogger("src.security.pii_masker").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

# ── App FastAPI ───────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mimetypes
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

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
_STARTUP_INDEX_ENABLED = env_bool("STARTUP_INDEX_ENABLED", True)
_STARTUP_WARMUP_ENABLED = env_bool("STARTUP_WARMUP_ENABLED", True)
_WATCHDOG_ENABLED = env_bool("WATCHDOG_ENABLED", True)
_WARMUP_FORCE_REINDEX_ON_DIM_MISMATCH = env_bool("WARMUP_FORCE_REINDEX_ON_DIM_MISMATCH", True)
_STARTUP_WARMUP_MODE = (os.getenv("STARTUP_WARMUP_MODE", "parallel") or "parallel").strip().lower()
_WARMUP_ENABLE_RERANKER_PRIME = env_bool("WARMUP_ENABLE_RERANKER_PRIME", True)
try:
    _WARMUP_STEP_DELAY_SECONDS = max(0.0, float(os.getenv("WARMUP_STEP_DELAY_SECONDS", "0.75")))
except ValueError:
    _WARMUP_STEP_DELAY_SECONDS = 0.75

def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False

def _is_first_worker() -> bool:
    """Uses a lock file so only one worker starts warmup/indexing.
    A lock older than 60s is considered stale (crash, Stop-Process, restart).
    In the same session, workers start in a few seconds → lock < 10s → not removed.
    """
    if os.path.exists(_LOCK_FILE):
        stale_reason = None
        try:
            with open(_LOCK_FILE, "r", encoding="utf-8") as f:
                raw_pid = f.read().strip()
            lock_pid = int(raw_pid) if raw_pid else 0
            if lock_pid and not _pid_is_alive(lock_pid):
                stale_reason = f"owner pid {lock_pid} absent"
        except Exception:
            stale_reason = "unreadable lock"

        if stale_reason is None:
            try:
                age = time.time() - os.path.getmtime(_LOCK_FILE)
                if age > 60:
                    stale_reason = f"stale lock ({age:.0f}s)"
            except Exception:
                stale_reason = "lock mtime unavailable"

        if stale_reason:
            try:
                os.remove(_LOCK_FILE)
                logger.info(f"[STARTUP] Lock removed ({stale_reason}).")
            except Exception:
                pass
    try:
        fd = os.open(_LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False

def _warmup() -> None:
    """Preloads runtime components.

    Available modes via STARTUP_WARMUP_MODE:
    - parallel: max speed, higher CPU at boot
    - phased: progressive startup, more stable CPU
    """
    import time

    def _load_embeddings():
        t = time.monotonic()
        try:
            from src.ingestion.vector_store import _get_embeddings, _get_client, _COLLECTION_NAME
            _get_embeddings()
            try:
                client = _get_client()
                count = client.count(_COLLECTION_NAME).count
                # Also check the dimension — a 384-dim collection with 30 points
                # will still be erased on the 1st get_store() call → better re-index now
                needs_reindex = False
                if count > 0:
                    try:
                        from src.ingestion.vector_store import _get_vector_size
                        current_dim = _get_vector_size()
                        coll_dim = client.get_collection(_COLLECTION_NAME).config.params.vectors.size
                        if coll_dim != current_dim:
                            logger.warning(f"[WARMUP] Dimension mismatch ({coll_dim} vs {current_dim}) → forced re-index.")
                            needs_reindex = True
                    except Exception as e:
                        logger.warning(f"[WARMUP] Dimension check failed: {e}")
                else:
                    logger.info("[WARMUP] Qdrant empty: background indexing scheduled (no force_reindex in warmup).")
                logger.info(f"[WARMUP] FastEmbed ready, Qdrant '{_COLLECTION_NAME}': {count} points ({time.monotonic() - t:.1f}s)")
                if needs_reindex and _WARMUP_FORCE_REINDEX_ON_DIM_MISMATCH:
                    from src.ingestion.run import index_data
                    index_data(force_reindex=True)
                    count2 = client.count(_COLLECTION_NAME).count
                    logger.info(f"[WARMUP] Re-indexation complete: {count2} points.")
            except Exception as e:
                logger.info(f"[WARMUP] FastEmbed ready ({time.monotonic() - t:.1f}s) (count check: {e})")
        except Exception as e:
            logger.warning(f"[WARMUP] FastEmbed failed: {e}")

    def _load_reranker():
        t = time.monotonic()
        try:
            from src.search.search import _get_reranker
            reranker = _get_reranker()
            if reranker:
                if _WARMUP_ENABLE_RERANKER_PRIME:
                    # Prime ONNX execution graph — without this the 1st real inference takes ~10s
                    list(reranker.rerank("warmup query", ["warmup passage"]))
                    logger.info(f"[WARMUP] Reranker ready + ONNX primed ({time.monotonic() - t:.1f}s)")
                else:
                    logger.info(f"[WARMUP] Reranker loaded (prime disabled) ({time.monotonic() - t:.1f}s)")
            else:
                logger.info(f"[WARMUP] Reranker unavailable ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] Reranker failed: {e}")

    def _load_bm25():
        t = time.monotonic()
        try:
            from src.search.search import _load_bm25
            _load_bm25()
            logger.info(f"[WARMUP] BM25 ready ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] BM25 failed: {e}")

    def _load_redis():
        t = time.monotonic()
        try:
            from src.caching.semantic_cache import _get_redis as _get_redis_cache
            import asyncio
            try:
                # If we are already in a loop (unlikely here since started by ThreadPoolExecutor)
                loop = asyncio.get_running_loop()
                loop.create_task(_get_redis_cache())
            except RuntimeError:
                # Otherwise we start a small loop
                asyncio.run(_get_redis_cache())
            logger.info(f"[WARMUP] Redis ready ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] Redis failed: {e}")

    def _load_llm():
        t = time.monotonic()
        try:
            # Force import of generator module → initializes Langfuse + creates LLM client
            # Without this, Langfuse initializes during the 1st request and adds ~2-3s
            import src.generation.generator as _gen  # noqa: F401
            try:
                # Prime callback stack (Langfuse) to avoid init on first request.
                _gen._callbacks("startup-warmup")
            except Exception:
                pass
            # Prime Groq HTTP connection (reformulation) — avoids ~3s cold start on 1st request
            if _gen._llm_reformulation:
                try:
                    _gen._llm_reformulation.invoke("ok", config={"max_tokens": 1})
                except Exception:
                    pass
            logger.info(f"[WARMUP] LLM + Langfuse ready ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] LLM init failed: {e}")

    t0 = time.monotonic()
    mode = _STARTUP_WARMUP_MODE
    if mode not in {"parallel", "phased"}:
        logger.warning("[WARMUP] STARTUP_WARMUP_MODE invalid (%s), fallback parallel.", mode)
        mode = "parallel"

    logger.info("[WARMUP] Mode: %s", mode)

    if mode == "parallel":
        threads = [
            threading.Thread(target=_load_embeddings, daemon=True),
            threading.Thread(target=_load_reranker,   daemon=True),
            threading.Thread(target=_load_llm,        daemon=True),
            threading.Thread(target=_load_redis,      daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Load BM25 after the embeddings/Qdrant phase to avoid showing
        # an obsolete corpus just before a forced re-indexation.
        _load_bm25()
    else:
        # WHY: In phased mode, we spread out expensive tasks to reduce CPU spikes.
        steps = [_load_redis, _load_llm, _load_embeddings, _load_bm25, _load_reranker]
        for i, step in enumerate(steps):
            step()
            if _WARMUP_STEP_DELAY_SECONDS > 0 and i < len(steps) - 1:
                time.sleep(_WARMUP_STEP_DELAY_SECONDS)

    logger.info(f"[WARMUP] Done ({time.monotonic() - t0:.1f}s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    first = _is_first_worker()
    if first:
        if _STARTUP_WARMUP_ENABLED:
            # BLOCKING preload of FastEmbed + Reranker ONNX before accepting requests
            # → eliminates cold start latency on first request (~4–10s without this)
            await asyncio.to_thread(_warmup)
        else:
            logger.info("[STARTUP] Warmup disabled (STARTUP_WARMUP_ENABLED=false).")

        if _STARTUP_INDEX_ENABLED:
            # WHY: Avoid memory spike of warmup + index_data in parallel (source of SIGKILL OOM).
            # Indexing starts after warmup in a separate thread.
            threading.Thread(target=index_data, kwargs={"force_reindex": False}, daemon=True).start()
        else:
            logger.info("[STARTUP] Initial indexing disabled (STARTUP_INDEX_ENABLED=false).")

        if _WATCHDOG_ENABLED:
            # Watchdog on data/sample/ to automatically reindex if a file changes
            start_watchdog()
        else:
            logger.info("[STARTUP] Watchdog disabled (WATCHDOG_ENABLED=false).")
    yield
    if first:
        if _WATCHDOG_ENABLED:
            stop_watchdog()
        try:
            os.remove(_LOCK_FILE)
        except OSError:
            pass


app = FastAPI(
    title="Oracle LoreKeeper",
    lifespan=lifespan,
    # Move Swagger UI away from /docs to avoid collision with React SPA route /docs
    docs_url="/api/swagger",
    redoc_url="/api/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

_allowed_origins = [o.strip() for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080"
).split(",") if o.strip()]



# Permissive CORS (dev and test)
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

# Static files (frontend) — no-cache in dev to avoid stale versions
_root_dir = os.path.dirname(__file__)
_frontend_react_candidates = [
    os.path.join(_root_dir, "frontend"),
    os.path.join(_root_dir, "src", "frontend-react"),
]
_frontend_react_dir = next((p for p in _frontend_react_candidates if os.path.isdir(p)), _frontend_react_candidates[0])
_frontend_react_dist = os.path.join(_frontend_react_dir, "dist")
_frontend_build_candidates = [
    os.path.join(_root_dir, "src", "frontend"),
    _frontend_react_dist,
    os.path.join(_root_dir, "frontend"),
]


def _ensure_frontend_build() -> None:
    """Build React frontend locally if no static frontend is available."""
    if _is_dev:
        return

    for build_dir in _frontend_build_candidates:
        if os.path.isfile(os.path.join(build_dir, "index.html")):
            return

    package_json = os.path.join(_frontend_react_dir, "package.json")
    if not os.path.isfile(package_json):
        return

    logger.info("Frontend not built: attempting automatic build (npm run build)")
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
        "Automatic frontend build failed. Install Node.js/npm or run manually: "
        f"cd {os.path.relpath(_frontend_react_dir, _root_dir)} && npm install && npm run build"
        + (f" | Detail: {last_error}" if last_error else "")
    )


_ensure_frontend_build()

_frontend_candidates = [
    *_frontend_build_candidates,
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
            # Dev only: disable cache to see changes immediately
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif path.startswith("/assets/"):
            # Prod: avoid obsolete assets behind some reverse proxies/CDNs.
            # We can relax this later when the deployment is stabilized.
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif path.endswith(".html") or path == "/":
            # Prod: HTML not cached (to detect new versions)
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheStaticMiddleware)

# Serve natively via spa_fallback rather than StaticFiles (avoids Starlette + Windows 404 bug)
# (Conditional mounting has been removed, we only use FileResponse)

# Catch-all SPA: serves index.html for /chat, /monitoring, etc.
# Must be AFTER API routes and AFTER /assets
from fastapi.responses import FileResponse as _FileResponse

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
        
    # Serve static files (assets/..., favicon.svg, icons.svg...)
    static_file = os.path.join(_frontend, full_path)
    if full_path and os.path.isfile(static_file):
        return _FileResponse(static_file)
        
    if full_path.startswith("assets/"):
        return JSONResponse({"error": "Asset not found", "path": static_file}, status_code=404)
    # All other routes → index.html (React Router handles client-side)
    if os.path.isfile(_index_file):
        return _FileResponse(_index_file)
    return JSONResponse(
        {
            "error": "Frontend not built",
            "detail": "Run the frontend build (npm run build) or start in Docker.",
        },
        status_code=503,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app", host="0.0.0.0", port=port, reload=_is_dev,
        reload_excludes=["*.lock", "*.pyc", "__pycache__"],
        workers=1 if not _is_dev else None,
    )
