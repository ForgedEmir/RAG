#!/bin/sh
# Lance FastAPI (port 8000) + MCP SSE (port 8001) en parallèle

# Serveur MCP SSE en arrière-plan
MCP_TRANSPORT=sse MCP_PORT=8001 python mcp_server.py &
MCP_PID=$!

# Serveur FastAPI principal (bloquant)
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --max-requests 500 \
  --max-requests-jitter 50 \
  --log-level info

# Si gunicorn s'arrête, on tue aussi le MCP
kill $MCP_PID
