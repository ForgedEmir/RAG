"""Oracle LoreKeeper — Point d'entrée FastAPI."""
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

# Silencer les logs HTTP externes (Supabase, Qdrant, OpenRouter) — trop verbeux en prod
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
    """Utilise un fichier lock pour qu'un seul worker lance le warmup/indexation.
    Un lock vieux de plus de 60s est considéré périmé (crash, Stop-Process, redémarrage).
    Dans la même session, les workers démarrent en quelques secondes → lock < 10s → non supprimé.
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
            stale_reason = "lock illisible"

        if stale_reason is None:
            try:
                age = time.time() - os.path.getmtime(_LOCK_FILE)
                if age > 60:
                    stale_reason = f"verrou périmé ({age:.0f}s)"
            except Exception:
                stale_reason = "mtime lock indisponible"

        if stale_reason:
            try:
                os.remove(_LOCK_FILE)
                logger.info(f"[STARTUP] Verrou supprimé ({stale_reason}).")
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
    """Pré-charge les composants runtime.

    Modes disponibles via STARTUP_WARMUP_MODE:
    - parallel: vitesse max, CPU plus élevé au boot
    - phased: démarrage progressif, CPU plus stable
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
                # Vérifie aussi la dimension — une collection 384-dim avec 30 points
                # sera quand même effacée au 1er appel get_store() → mieux vaut re-indexer maintenant
                needs_reindex = False
                if count > 0:
                    try:
                        from src.ingestion.vector_store import _get_vector_size
                        current_dim = _get_vector_size()
                        coll_dim = client.get_collection(_COLLECTION_NAME).config.params.vectors.size
                        if coll_dim != current_dim:
                            logger.warning(f"[WARMUP] Dimension mismatch ({coll_dim} vs {current_dim}) → re-indexation forcée.")
                            needs_reindex = True
                    except Exception as e:
                        logger.warning(f"[WARMUP] Vérification dimension impossible : {e}")
                else:
                    logger.info("[WARMUP] Qdrant vide: indexation en arrière-plan prévue (pas de force_reindex en warmup).")
                logger.info(f"[WARMUP] FastEmbed prêt, Qdrant '{_COLLECTION_NAME}': {count} points ({time.monotonic() - t:.1f}s)")
                if needs_reindex and _WARMUP_FORCE_REINDEX_ON_DIM_MISMATCH:
                    from src.ingestion.run import index_data
                    index_data(force_reindex=True)
                    count2 = client.count(_COLLECTION_NAME).count
                    logger.info(f"[WARMUP] Re-indexation terminée : {count2} points.")
            except Exception as e:
                logger.info(f"[WARMUP] FastEmbed prêt ({time.monotonic() - t:.1f}s) (count check: {e})")
        except Exception as e:
            logger.warning(f"[WARMUP] FastEmbed échoué : {e}")

    def _load_reranker():
        t = time.monotonic()
        try:
            from src.search.search import _get_reranker
            reranker = _get_reranker()
            if reranker:
                if _WARMUP_ENABLE_RERANKER_PRIME:
                    # Prime ONNX execution graph — sans ça la 1ère inférence réelle prend ~10s
                    list(reranker.rerank("warmup query", ["warmup passage"]))
                    logger.info(f"[WARMUP] Reranker prêt + ONNX primed ({time.monotonic() - t:.1f}s)")
                else:
                    logger.info(f"[WARMUP] Reranker chargé (prime désactivé) ({time.monotonic() - t:.1f}s)")
            else:
                logger.info(f"[WARMUP] Reranker indisponible ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] Reranker échoué : {e}")

    def _load_bm25():
        t = time.monotonic()
        try:
            from src.search.search import _load_bm25
            _load_bm25()
            logger.info(f"[WARMUP] BM25 prêt ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] BM25 échoué : {e}")

    def _load_redis():
        t = time.monotonic()
        try:
            from src.caching.semantic_cache import _get_redis as _get_redis_cache
            import asyncio
            try:
                # Si on est déjà dans une boucle (peu probable ici car lancé par ThreadPoolExecutor)
                loop = asyncio.get_running_loop()
                loop.create_task(_get_redis_cache())
            except RuntimeError:
                # Sinon on lance une petite boucle
                asyncio.run(_get_redis_cache())
            logger.info(f"[WARMUP] Redis prêt ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] Redis échoué : {e}")

    def _load_llm():
        t = time.monotonic()
        try:
            # Force l'import du module generator → initialise Langfuse + crée le client LLM
            # Sans ça, Langfuse s'initialise pendant la 1ère requête et ajoute ~2-3s
            import src.generation.generator as _gen  # noqa: F401
            try:
                # Prime callback stack (Langfuse) pour éviter l'init à la première requête.
                _gen._callbacks("startup-warmup")
            except Exception:
                pass
            # Prime la connexion HTTP Groq (reformulation) — évite le cold start ~3s sur la 1ère requête
            if _gen._llm_reformulation:
                try:
                    _gen._llm_reformulation.invoke("ok", config={"max_tokens": 1})
                except Exception:
                    pass
            logger.info(f"[WARMUP] LLM + Langfuse prêts ({time.monotonic() - t:.1f}s)")
        except Exception as e:
            logger.warning(f"[WARMUP] LLM init échoué : {e}")

    t0 = time.monotonic()
    mode = _STARTUP_WARMUP_MODE
    if mode not in {"parallel", "phased"}:
        logger.warning("[WARMUP] STARTUP_WARMUP_MODE invalide (%s), fallback parallel.", mode)
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

        # Charge BM25 après la phase embeddings/Qdrant pour éviter d'afficher
        # un corpus obsolète juste avant une réindexation forcée.
        _load_bm25()
    else:
        # WHY: En mode phased, on étale les tâches coûteuses pour réduire les pics CPU.
        steps = [_load_redis, _load_llm, _load_embeddings, _load_bm25, _load_reranker]
        for i, step in enumerate(steps):
            step()
            if _WARMUP_STEP_DELAY_SECONDS > 0 and i < len(steps) - 1:
                time.sleep(_WARMUP_STEP_DELAY_SECONDS)

    logger.info(f"[WARMUP] Terminé ({time.monotonic() - t0:.1f}s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    first = _is_first_worker()
    if first:
        if _STARTUP_WARMUP_ENABLED:
            # Pré-charge FastEmbed + Reranker ONNX de façon BLOQUANTE avant d'accepter des requêtes
            # → élimine la latence à froid sur la première requête (~4–10s sans ça)
            await asyncio.to_thread(_warmup)
        else:
            logger.info("[STARTUP] Warmup désactivé (STARTUP_WARMUP_ENABLED=false).")

        if _STARTUP_INDEX_ENABLED:
            # WHY: Évite le pic mémoire warmup + index_data en parallèle (source de SIGKILL OOM).
            # L'indexation démarre après warmup dans un thread séparé.
            threading.Thread(target=index_data, kwargs={"force_reindex": False}, daemon=True).start()
        else:
            logger.info("[STARTUP] Indexation initiale désactivée (STARTUP_INDEX_ENABLED=false).")

        if _WATCHDOG_ENABLED:
            # Watchdog sur data/sample/ pour réindexer automatiquement si un fichier change
            start_watchdog()
        else:
            logger.info("[STARTUP] Watchdog désactivé (WATCHDOG_ENABLED=false).")
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



# CORS permissif comme avant (dev et test)
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
        f"cd {os.path.relpath(_frontend_react_dir, _root_dir)} && npm install && npm run build"
        + (f" | Détail: {last_error}" if last_error else "")
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

# Servir nativement via spa_fallback plutôt que StaticFiles (évite le bug 404 Starlette + Windows)
# (Le montage conditionnel a été retiré, nous utilisons uniquement FileResponse)

# Catch-all SPA : sert index.html pour /chat, /monitoring, etc.
# Doit être APRÈS les routes API et APRÈS /assets
from fastapi.responses import FileResponse as _FileResponse

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
        
    # Servir les fichiers statiques (assets/..., favicon.svg, icons.svg…)
    static_file = os.path.join(_frontend, full_path)
    if full_path and os.path.isfile(static_file):
        return _FileResponse(static_file)
        
    if full_path.startswith("assets/"):
        return JSONResponse({"error": "Asset introuvable", "path": static_file}, status_code=404)
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
    uvicorn.run(
        "main:app", host="0.0.0.0", port=port, reload=_is_dev,
        reload_excludes=["*.lock", "*.pyc", "__pycache__"],
        workers=1 if not _is_dev else None,
    )
