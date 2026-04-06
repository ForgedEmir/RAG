FROM node:20 AS frontend
WORKDIR /build
ARG FRONTEND_CACHE_BUST=2026-04-06-1
COPY src/frontend-react/package.json src/frontend-react/package-lock.json ./
RUN npm ci
COPY src/frontend-react/ ./
RUN echo "FRONTEND_CACHE_BUST=${FRONTEND_CACHE_BUST}" \
    && rm -rf /output \
    && npx vite build --outDir /output \
    && ls -la /output/ \
    && grep -n "assets/index-" /output/index.html

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 poppler-utils tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN rm -rf /app/src/frontend/assets /app/src/frontend/index.html
COPY --from=frontend /output/ /app/src/frontend/

RUN chmod +x start.sh

# Port 8000 : API + frontend web
# Port 8001 : MCP SSE (Claude Desktop, Cursor, etc.)
EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["./start.sh"]
