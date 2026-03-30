"""Oracle LoreKeeper — Point d'entrée FastAPI."""
import os
import logging
from collections import deque
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv(override=True)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    index_data(force_reindex=False)
    yield


app = FastAPI(title="Oracle LoreKeeper", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app, _log_buffer)

# Fichiers statiques (frontend)
_frontend = os.path.join(os.path.dirname(__file__), "src", "frontend")
app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
