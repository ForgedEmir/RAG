# Oracle LoreKeeper

<div align="center">

### Production-minded RAG backend for game lore

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.13x-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![Qdrant](https://img.shields.io/badge/VectorDB-Qdrant-EA4335)
![Redis](https://img.shields.io/badge/Cache-Redis-D82C20?logo=redis&logoColor=white)
![Supabase](https://img.shields.io/badge/Auth%20%26%20Data-Supabase-3FCF8E?logo=supabase&logoColor=white)

Hybrid retrieval, SSE streaming answers, monitoring, and MCP support in one clean stack.

</div>

## Snapshot

| Area | Stack | Status |
|---|---|---|
| API | FastAPI + Gunicorn/Uvicorn | Stable |
| Retrieval | Qdrant + BM25 + smart rerank | Stable |
| Embeddings | FastEmbed ONNX (no torch) | Stable |
| Auth/Data | Supabase | Stable |
| Cache/limits | Redis + SlowAPI | Stable |
| Monitoring | API monitoring + tracker | Stable |

## What makes it solid

- single primary answer pipeline: POST /api/ask
- grounded retrieval-first flow before generation
- no PyTorch runtime dependency for embedding/rerank
- production-friendly process model and shared cache
- built-in feedback, tracking, and security checks

## Request lifecycle

```text
Client
       -> /api/ask
       -> security validation + PII masking
       -> optional reformulation
       -> hybrid retrieval (vector + BM25)
       -> optional smart rerank
       -> LLM generation (SSE stream)
       -> persist messages + tracking + cache
```

## Current health

- unit suite: 127 passed, 6 skipped, 0 failed
- skipped tests are explicit heavy load tests (opt-in)

Known limits:

- strict 10s SLA is not reliable on uncached 15-concurrent traffic
- provider 429 rate limits can increase tail latency
- Gunicorn is Linux-oriented; Docker is the recommended production-like runtime on Windows hosts

## Recent latency checks (April 2026)

| Scenario | Concurrency | Success | <=10s SLA |
|---|---:|---:|---:|
| cache-friendly traffic | 15 | 15/15 | 15/15 |
| uncached unique traffic | 15 | 15/15 | 3/15 |

Interpretation:

- functionally stable: yes
- strict low-latency under heavy uncached burst: not yet

## Quickstart

### 1) Local setup

```bash
git clone <repo-url>
cd Oracle-LoreKeeper-dev

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
```

Then fill .env with your keys (LLM, Qdrant, Supabase).

### 2) Run

Development:

```bash
python main.py
```

Docker / production-like local run:

```bash
docker compose up --build
```

- API: http://localhost:8000
- MCP SSE: http://localhost:8001

## Recommended production profile

```env
APP_ENV=production
ENV=production

RAG_PROFILE=balanced
REDIS_URL=redis://redis:6379

WEB_CONCURRENCY=2
BACKGROUND_MAX_WORKERS=16
GUNICORN_TIMEOUT=120
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEPALIVE=10

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
RERANKER_ENABLED=true
SMART_RERANK_ENABLED=true
RERANK_SIMPLE_QUERIES=false
RERANKER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
RERANKER_MAX_INPUT=4

HYDE_ENABLED=true
HYDE_TIMEOUT_SECONDS=3.5
MAX_RESPONSE_SECONDS=10

QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH=true
```

## Core APIs

- GET /health
- POST /api/ask (SSE)
- POST /api/feedback
- POST /api/reindex (monitoring key)
- GET /api/monitoring/*
- GET/POST /api/monitoring/reformulation
- GET /api/monitoring/search-switches (read-only)

## Testing

Unit suite:

```bash
python -m pytest src/test-unitaires -q
```

Load tests (explicit opt-in):

```bash
set RUN_LOAD_TESTS=true
python -m pytest src/test-unitaires/test_load.py -q
```

## Repo hygiene

- .env and .env.* are ignored by git
- .env.example is versioned
- dependencies are explicit and runtime-focused

## More docs

See DOCUMENTATION.md for detailed architecture, deployment checklist, and tuning notes.
