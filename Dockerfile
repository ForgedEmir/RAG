FROM node:20-slim AS frontend
WORKDIR /build
COPY src/frontend-react/package.json src/frontend-react/package-lock.json ./
RUN npm ci
COPY src/frontend-react/ ./
RUN npx vite build --outDir /output && ls -la /output/

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 poppler-utils tesseract-ocr curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /output/ /app/src/frontend/

RUN chmod +x start.sh

# Port 8000 : API + frontend web
# Port 8001 : MCP SSE (Claude Desktop, Cursor, etc.)
EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["./start.sh"]
