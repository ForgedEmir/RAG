#!/bin/sh
# Lance FastAPI (port 8000) + MCP SSE (port 8001) en parallèle
# Gestion propre des signaux pour arrêt gracieux

cleanup() {
    echo "[start] Arrêt en cours..."
    kill -TERM "$MCP_PID" 2>/dev/null
    kill -TERM "$GUNICORN_PID" 2>/dev/null
    wait "$MCP_PID" 2>/dev/null
    wait "$GUNICORN_PID" 2>/dev/null
    exit 0
}

trap cleanup SIGTERM SIGINT

# Serveur MCP SSE en arrière-plan
MCP_TRANSPORT=sse MCP_PORT=8001 python mcp_server.py &
MCP_PID=$!

# Serveur FastAPI principal
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers "${GUNICORN_WORKERS:-2}" \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --max-requests 500 \
  --max-requests-jitter 50 \
  --log-level info &
GUNICORN_PID=$!

wait "$GUNICORN_PID"
cleanup
