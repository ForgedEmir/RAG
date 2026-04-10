#!/bin/sh
# Lance FastAPI (port 8000) + MCP SSE (port 8001) en parallèle

# Serveur MCP SSE en arrière-plan
MCP_TRANSPORT=sse MCP_PORT=8001 python mcp_server.py &
MCP_PID=$!

cleanup() {
  kill "$MCP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Réglages par défaut pour une charge modérée (~15 utilisateurs concurrents).
WEB_CONCURRENCY=${WEB_CONCURRENCY:-4}
BACKGROUND_MAX_WORKERS=${BACKGROUND_MAX_WORKERS:-16}
GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-120}
GUNICORN_GRACEFUL_TIMEOUT=${GUNICORN_GRACEFUL_TIMEOUT:-30}
GUNICORN_KEEPALIVE=${GUNICORN_KEEPALIVE:-10}

export BACKGROUND_MAX_WORKERS

# Serveur FastAPI principal (bloquant)
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers "$WEB_CONCURRENCY" \
  --bind 0.0.0.0:8000 \
  --timeout "$GUNICORN_TIMEOUT" \
  --graceful-timeout "$GUNICORN_GRACEFUL_TIMEOUT" \
  --keep-alive "$GUNICORN_KEEPALIVE" \
  --max-requests 2000 \
  --max-requests-jitter 200 \
  --log-level info
