# Oracle LoreKeeper

<div align="center">

**Production-grade RAG backend for game lore — Aethelgard Online**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant-EA4335?logo=qdrant&logoColor=white)
![Redis](https://img.shields.io/badge/Cache-Redis-D82C20?logo=redis&logoColor=white)
![Supabase](https://img.shields.io/badge/Auth_%26_Data-Supabase-3FCF8E?logo=supabase&logoColor=white)
![Cerebras](https://img.shields.io/badge/LLM-Cerebras-FF6B35)

*Hybrid retrieval · SSE streaming · Multi-user · Security layers · MCP integration*

</div>

---

## Overview

Oracle LoreKeeper is a retrieval-augmented generation (RAG) system that answers player questions about the lore of **Aethelgard Online**. It retrieves grounded, source-backed answers from indexed game documents, streams them in real time, and integrates directly into Minecraft via a Paper plugin.

**Key design principles:**
- Single, clean answer pipeline (`POST /api/ask`)
- No PyTorch runtime — all embeddings/reranking via ONNX (FastEmbed)
- Config-driven: every provider, model, and feature flag is an environment variable
- Production-ready: rate limiting, semantic cache, security validation, monitoring dashboard

---

## Stack at a Glance

| Layer | Technology | Notes |
|---|---|---|
| API | FastAPI + Gunicorn/Uvicorn | Async, streaming, self-documenting |
| Vector DB | Qdrant | Cloud or local mode |
| Embeddings | FastEmbed ONNX | Multilingual MiniLM (384-dim) — no GPU required |
| Reranker | FastEmbed ONNX | Xenova/ms-marco cross-encoder — smart activation |
| Lexical search | BM25 (rank-bm25) | French stopword support |
| LLM Primary | Cerebras (`llama3.1-8b`) | ~500 ms, fast inference |
| LLM Fallback | Groq (`llama-3.3-70b-versatile`) | Auto-activated on 429s |
| Auth & events | Supabase | PostgreSQL-backed, JWT auth |
| Cache & limits | Redis + SlowAPI | Semantic cache + per-user rate limiting |
| Frontend | React + Vite + Tailwind | Served statically by FastAPI |
| Observability | Langfuse (optional) | Full pipeline tracing |
| Security | Lakera Guard (optional) + regex chunk checks | Injection detection, PII masking |
| Quality | Langfuse | LLM-as-Judge, pipeline tracing, evaluation scores |

---

## Request Lifecycle

```
Client → POST /api/ask
          │
          ├── Auth (JWT or guest)
          ├── PII masking
          ├── Security validation (Lakera Guard, optional)
          ├── Semantic cache lookup  ──► cached? return immediately
          │
          ├── Parallel context fetch
          │   ├── Conversation history (last 5 exchanges)
          │   ├── User summary (150-word LLM-generated profile)
          │   └── Vector memories (semantic similarity)
          │
          ├── Query reformulation (optional, makes question self-contained)
          │
          ├── Hybrid retrieval
          │   ├── Vector search (Qdrant)
          │   ├── BM25 fallback (if vector signal weak)
          │   ├── RRF fusion
          │   ├── Smart rerank (cross-encoder, conditionally activated)
          │   └── HyDE fallback (hypothetical doc embeddings, if low score)
          │
          ├── LLM generation → SSE stream to client
          │
          └── Background: persist · cache · track · update memory
```

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm (required to build the frontend)
- Docker (recommended for production-like local run)
- API keys: Cerebras (LLM), Qdrant (vector DB), Supabase (auth/data)

### 1. Clone & install

```bash
git clone <repo-url>
cd Oracle-LoreKeeper

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt

# Build the frontend (requires Node.js 18+)
cd src/frontend-react && npm install && npm run build && cd ../..
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — minimum required keys:
# LLM_API_KEY, QDRANT_URL, QDRANT_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
```

See [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) for full environment variable reference.

### 3. Run

**Development:**
```bash
python main.py
# → API + frontend at http://localhost:8000
```

**Production (Docker):**
```bash
docker compose up --build
# → API at http://localhost:8000
# → MCP server at http://localhost:8001
```

**Makefile shortcuts:**
```bash
make setup      # First-time setup (venv + .env + index)
make run        # Dev server
make docker-up  # Docker start
make test       # Run unit tests
make index      # Force reindex
```

---

## API Endpoints

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/health` | GET | — | Component health check |
| `/api/ask` | POST | JWT / guest | Main RAG endpoint (SSE stream) |
| `/api/feedback` | POST | JWT / guest | Submit rating (1–5) |
| `/api/auth/config` | GET | — | Supabase public config |
| `/api/auth/me` | GET | JWT | Current user ID |
| `/api/swagger` | GET | — | OpenAPI Swagger UI |
| `/api/redoc` | GET | — | OpenAPI ReDoc UI |
| `/api/feedback/vote` | POST | JWT / guest | Submit thumbs up/down (-1 / +1) by trace_id |
| `/api/conversations` | GET | JWT / guest | Get conversation history for a session |
| `/api/conversations/list` | GET | JWT / guest | List all conversations for current user |
| `/api/conversations/messages` | GET | JWT / guest | Get raw messages for a session |
| `/api/conversations` | DELETE | JWT / guest | Delete conversation history |
| `/api/reindex` | POST | monitoring key | Force reindex of data/sample/ |
| `/api/monitoring/stats` | GET | monitoring key | Global usage statistics |
| `/api/monitoring/pipeline` | GET | monitoring key | Retrieval pipeline details |
| `/api/monitoring/features` | GET | monitoring key | Full feature health dashboard |
| `/api/monitoring/reformulation` | GET / POST | monitoring key | Read / toggle reformulation |
| `/api/monitoring/reformulation/history` | GET | monitoring key | Last 20 reformulations |
| `/api/monitoring/search-switches` | GET | monitoring key | Current search config (read-only) |
| `/api/monitoring/runtime-profile` | GET | monitoring key | Active profile (fast / balanced / quality) |
| `/api/monitoring/contextual-retrieval` | GET | monitoring key | % of chunks with doc_summary enrichment |
| `/api/monitoring/user-memories` | GET | monitoring key | Last 20 user memory summaries |
| `/api/monitoring/feedbacks` | GET | monitoring key | Recent feedback events |
| `/api/monitoring/pii` | GET | monitoring key | PII masking history |
| `/api/monitoring/logs` | GET | monitoring key | In-memory system log buffer |
| `/api/cache/stats` | GET | monitoring key | Semantic cache statistics |
| `/api/admin/sources` | GET | monitoring key | Indexed source files |
| `/api/admin/delete` | DELETE | monitoring key | Remove a source file |

**Request body for `/api/ask`:**
```json
{
  "question": "Who is Alaric the Fallen?",
  "session_id": "uuid-v4",
  "user_id": "guest_uuid-v4"
}
```

**Response:** Server-Sent Events stream
```
data: {"type": "text", "text": "Alaric was..."}
data: {"type": "text", "text": " a general who..."}
data: {"type": "done", "trace_id": "...", "model": "llama3.1-8b"}
```

---

## Testing

**Unit suite:**
```bash
python -m pytest src/test-unitaires -q
```

**Targeted run after retrieval changes:**
```bash
python -m pytest src/test-unitaires/test_search.py src/test-unitaires/test_routes.py -q
```

**Load tests (opt-in):**
```bash
# Windows:
set RUN_LOAD_TESTS=true
# Linux/macOS:
export RUN_LOAD_TESTS=true

python -m pytest src/test-unitaires/test_load.py -q
```

**Locust load testing:**
```bash
set LOCUST_BEARER_TOKEN=<your_jwt>
locust -f src/test-unitaires/locustfile.py --host http://localhost:8000
```

---

## MCP Server

Oracle LoreKeeper exposes a [Model Context Protocol](https://modelcontextprotocol.io) server, allowing any MCP-compatible client (Claude Desktop, Cursor, etc.) to query the lore knowledge base directly as a tool.

**Start the server:**
```bash
# Stdio mode (local, embedded in client)
python mcp_server.py

# SSE mode (remote, network-accessible)
export MCP_TRANSPORT=sse
export MCP_PORT=8001
python mcp_server.py
```

**Claude Desktop config** (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "lorekeeper": {
      "command": "python",
      "args": ["C:/path/to/mcp_server.py"],
      "env": {
        "LLM_API_KEY": "csk_...",
        "QDRANT_URL": "https://...",
        "QDRANT_API_KEY": "..."
      }
    }
  }
}
```

Once configured, Claude can invoke the Oracle knowledge base as a tool during any conversation.

---

## Production Profile

Recommended `.env` settings for deployment:

```env
APP_ENV=production
ENV=production
RAG_PROFILE=balanced

WEB_CONCURRENCY=2
BACKGROUND_MAX_WORKERS=8
GUNICORN_TIMEOUT=120
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEPALIVE=10

REDIS_URL=redis://redis:6379

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
QDRANT_VECTOR_SIZE=384
FASTEMBED_CACHE_PATH=/app/fastembed_cache
HF_TOKEN=hf_xxx
RERANKER_ENABLED=true
SMART_RERANK_ENABLED=true
RERANKER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
RERANKER_MAX_INPUT=4

HYDE_ENABLED=true
HYDE_TIMEOUT_SECONDS=3.5
MAX_RESPONSE_SECONDS=10

QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH=true
```

For stable model downloads and startup speed in production:

1. Set `HF_TOKEN` in your deployment environment.
2. Keep `FASTEMBED_CACHE_PATH` on a persistent volume (example path: `/app/fastembed_cache`).

---

## Repo Hygiene

- `.env` and `.env.*` are git-ignored
- `.env.example` is versioned with all variables documented
- No hardcoded API keys or base URLs anywhere in the codebase

## CI/CD Status

No CI/CD workflow is currently configured in this repository.

---

## Full Documentation

See [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md) for:
- Detailed architecture per component
- Full environment variable reference
- Deployment checklist (Coolify)
- Ingestion pipeline deep-dive
- Security layers explained
- Troubleshooting guide
- MCP server setup
