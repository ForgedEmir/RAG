#!/bin/sh
# Lance FastAPI (port 8000) + MCP SSE (port 8001) en parallèle

# WHY (T12 leak): previously the MCP server launched without MCP_TENANT_ID,
# defaulting to the empty/global tenant. In multi-tenant deployments, this
# meant the MCP server bypassed all tenant filters, exposing every tenant's
# data. Now we refuse to start the MCP server if MCP_TENANT_ID is empty
# unless MULTI_TENANT=false (explicit single-tenant opt-in).

if [ -z "$MCP_TENANT_ID" ] && [ "$MULTI_TENANT" != "false" ]; then
  echo "[START] WARNING: MCP_TENANT_ID is empty and MULTI_TENANT is not 'false'." >&2
  echo "[START] The MCP server will default to the global tenant and bypass all" >&2
  echo "[START] tenant filters. This is unsafe in multi-tenant deployments." >&2
  echo "[START] Set MCP_TENANT_ID=<tenant_uuid> for per-tenant deployments, or" >&2
  echo "[START] set MULTI_TENANT=false to acknowledge single-tenant mode." >&2
  echo "[START] Skipping MCP server start. FastAPI will still run." >&2
  MCP_PID=""
else
  MCP_TRANSPORT=sse MCP_PORT=8001 python mcp_server.py &
  MCP_PID=$!
fi

cleanup() {
  [ -n "$MCP_PID" ] && kill "$MCP_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Réglages par défaut orientés stabilité mémoire (les valeurs restent surchargeables via env).
WEB_CONCURRENCY=${WEB_CONCURRENCY:-2}
BACKGROUND_MAX_WORKERS=${BACKGROUND_MAX_WORKERS:-8}
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
