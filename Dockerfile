FROM node:20 AS frontend
WORKDIR /build
ARG FRONTEND_CACHE_BUST=2026-04-06-1
ARG VITE_ALLOW_SELF_REGISTER=false
ARG VITE_MICROSOFT_AUTH_ENABLED=false
ENV VITE_ALLOW_SELF_REGISTER=$VITE_ALLOW_SELF_REGISTER
ENV VITE_MICROSOFT_AUTH_ENABLED=$VITE_MICROSOFT_AUTH_ENABLED
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN echo "FRONTEND_CACHE_BUST=${FRONTEND_CACHE_BUST}" \
    && rm -rf /output \
    && npx vite build --outDir /output \
    && ls -la /output/ \
    && grep -n "assets/index-" /output/index.html

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 poppler-utils tesseract-ocr curl \
    libreoffice-impress libreoffice-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# spacy était requis par Unstructured (optionnel depuis v2.2)
# Si besoin : décommenter + ajouter 'spacy' dans requirements.txt
# RUN python -m spacy download en_core_web_sm

COPY . .
RUN rm -rf /app/src/frontend/assets /app/src/frontend/index.html
COPY --from=frontend /output/ /app/src/frontend/

RUN sed -i 's/\r$//' scripts/start.sh && chmod +x scripts/start.sh

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data/sample /app/logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["/bin/sh", "./scripts/start.sh"]
