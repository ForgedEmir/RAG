# Oracle LoreKeeper

<div align="center">

**Production-grade RAG backend — hybrid retrieval, SSE streaming, multi-user, MCP-ready**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant-EA4335?logo=qdrant&logoColor=white)
![Redis](https://img.shields.io/badge/Cache-Redis-D82C20?logo=redis&logoColor=white)
![Supabase](https://img.shields.io/badge/Auth_%26_Data-Supabase-3FCF8E?logo=supabase&logoColor=white)
![Cerebras](https://img.shields.io/badge/LLM-Cerebras-FF6B35?logo=cerebras&logoColor=white)
![React](https://img.shields.io/badge/Frontend-React_%2B_Vite-61DAFB?logo=react&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-45%20unit-2ea44f)

[![Open in Coolify](https://img.shields.io/badge/Deploy-Coolify-0ea5e9)](https://github.com/ForgedEmir/RAG)
[![MCP](https://img.shields.io/badge/MCP-Protocol-7C3AED?logo=modelcontextprotocol&logoColor=white)](https://modelcontextprotocol.io)

*Zéro PyTorch · Pas de GPU requis · Config-driven · Pipeline traçable*

</div>

---

## What This Is

Oracle LoreKeeper is a **production-grade Retrieval-Augmented Generation (RAG)** system designed for game lore — players ask questions, the system retrieves grounded answers from indexed documents and streams them in real-time.

Built for **Aethelgard Online**, a Minecraft MMORPG, it integrates directly via a Paper plugin and an MCP server for AI-client access (Claude Desktop, Cursor, etc.)

**Production-deployed on Coolify** — fully containerized, load-tested, and running.

---

## Why This Repo

| Problem | Solution |
|---|---|
| LLMs hallucinate lore answers | Hybrid retrieval (vector + BM25) + reranking + source citations |
| Slow response times are immersion-breaking | Cerebras inference (~500ms) + Redis semantic cache + SSE streaming |
| Players need real-time answers | Paper plugin ↔ MCP server direct integration |
| Multi-player context matters | User memory summaries + conversation history per session |
| Production reliability | Rate limiting, PII masking, security validation, monitoring dashboard |

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│   Client     │     │              Oracle LoreKeeper              │
│  (React /   │────▶│                                              │
│   Minecraft) │     │  POST /api/ask → Auth → PII → Security      │
└─────────────┘     │                   ↓                          │
                    │         ┌──────────────┐                     │
┌─────────────┐     │         │ Semantic     │ (cache hit → return)│
│  MCP Client  │────▶│         │ Cache (Redis) │                     │
│(Claude, etc.)│     │         └──────┬───────┘                     │
└─────────────┘     │                ↓ (miss)                      │
                    │         ┌────────────────┐                    │
                    │         │ Parallel       │                    │
                    │         │ Context Fetch  │ ← conversation     │
                    │         │                │ ← user memory      │
                    │         │                │ ← vector memories  │
                    │         └───────┬────────┘                    │
                    │                 ↓                             │
                    │         ┌────────────────┐                    │
                    │         │ Hybrid Retrieval│ ← Qdrant + BM25   │
                    │         │ → RRF fusion   │ ← reranker        │
                    │         │ → HyDE fallback│                    │
                    │         └───────┬────────┘                    │
                    │                 ↓                             │
                    │         ┌────────────────┐                    │
                    │         │  LLM (Cerebras │                    │
                    │         │  / Groq)       │ → SSE stream       │
                    │         └────────────────┘                    │
                    │                 ↓                             │
                    │         Background: cache · persist · track   │
                    └──────────────────────────────────────────────┘
```

---

## Stack

| Layer | Technology | Why |
|---|---|---|
| **API** | FastAPI + Gunicorn/Uvicorn | Async, SSE streaming, auto-docs |
| **Vector DB** | Qdrant | Cloud-native, fast, good filtering |
| **Embeddings** | FastEmbed ONNX (MiniLM 384d) | No GPU, no PyTorch, 5ms inference |
| **Reranker** | FastEmbed ONNX (cross-encoder) | Conditional activation — smart rerank |
| **Lexical** | BM25 (rank-bm25) | French stopwords, recovers vector misses |
| **LLM** | Cerebras (llama3.1-8b) / Groq fallback | ~500ms inference, auto-failover |
| **Auth** | Supabase (PostgreSQL + JWT) | Serverless, row-level security |
| **Cache** | Redis + SlowAPI | Semantic cache + rate limiting |
| **Security** | Lakera Guard + regex PII mask | Injection detection, GDPR compliance |
| **Frontend** | React + Vite + Tailwind | Static, served by FastAPI |
| **Observability** | Langfuse | LLM-as-Judge, full trace → eval score |
| **Integration** | MCP Server (stdio/SSE) | Claude Desktop, Cursor, any MCP client |
| **Deploy** | Docker + Coolify | 2-command startup, zero-downtime |

---

## Quickstart

### Requirements

- Python 3.11+, Node.js 18+, Docker (optional)

```bash
# Clone
git clone https://github.com/ForgedEmir/RAG.git
cd RAG

# Backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd src/frontend-react && npm install && npm run build && cd ../..

# Configure
cp .env.example .env
# → Set LLM_API_KEY, QDRANT_URL, QDRANT_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

# Run
python main.py
# → http://localhost:8000
```

### Docker (production)

```bash
docker compose up --build
# → API:8000  ·  MCP:8001
```

### Makefile

```bash
make setup      # First-time setup
make run        # Dev server
make docker-up  # Production
make test       # 45+ unit tests
make index      # Force reindex
```

---

## API Endpoints (16+)

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/ask` | POST | JWT/guest | **Main RAG endpoint** — SSE stream |
| `/api/feedback/vote` | POST | JWT/guest | Thumbs up/down by trace_id |
| `/api/conversations` | GET/DELETE | JWT/guest | Session conversation history |
| `/api/monitoring/stats` | GET | monitoring key | Global usage & pipeline health |
| `/api/cache/stats` | GET | monitoring key | Semantic cache hit rates |
| `/api/admin/sources` | GET | monitoring key | Indexed source files |
| `/health` | GET | — | Component health check |
| *+ 9 more* | | | See full docs below |

**Request:**
```json
POST /api/ask
{
  "question": "Who is Alaric the Fallen?",
  "session_id": "uuid-v4",
  "user_id": "guest_uuid-v4"
}
```

**Response:** Server-Sent Events
```
data: {"type": "text", "text": "Alaric was a general who..."}
data: {"type": "done", "trace_id": "...", "model": "llama3.1-8b"}
```

---

## Testing

```bash
# All unit tests (45+)
python -m pytest src/test-unitaires -q

# Search-specific (after retrieval changes)
python -m pytest src/test-unitaires/test_search.py -q

# Load testing with Locust
locust -f src/test-unitaires/locustfile.py --host http://localhost:8000
```

---

## MCP Integration

Claude Desktop, Cursor, or any MCP client can query the lore directly.

```json
{
  "mcpServers": {
    "lorekeeper": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": { "LLM_API_KEY": "...", "QDRANT_URL": "...", "QDRANT_API_KEY": "..." }
    }
  }
}
```

---

## Production Profile

Key `.env` settings for deployment:

```env
RAG_PROFILE=balanced
WEB_CONCURRENCY=2
REDIS_URL=redis://redis:6379
QDRANT_VECTOR_SIZE=384
RERANKER_ENABLED=true
HYDE_ENABLED=true
SMART_RERANK_ENABLED=true
```

Full reference → [`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md)

---

## Key Design Decisions

- **No PyTorch runtime** → All embeddings/reranking via ONNX (FastEmbed). Docker image stays small, no GPU needed.
- **Config-driven** → Every provider, model, feature flag is an env var. No hardcoded secrets.
- **HyDE + BM25 fallbacks** → If vector retrieval score is weak, it tries hypothetical document embeddings and lexical search before giving up.
- **Smart rerank** → Cross-encoder only activates when the top-1 vector score is below threshold. Saves latency when the primary result is already good.
- **Single answer pipeline** → One endpoint (`/api/ask`) does everything. Simple to integrate, simple to monitor.

---

## Community & Contributing

| File | Purpose |
|---|---|
| [`LICENSE`](LICENSE) | MIT — free to use, modify, distribute |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute, PR guidelines, code style |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Community standards |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability |
| [Bug report template](.github/ISSUE_TEMPLATE/bug_report.md) | For issues |
| [Feature request template](.github/ISSUE_TEMPLATE/feature_request.md) | For suggestions |
| [PR template](.github/PULL_REQUEST_TEMPLATE.md) | For pull requests |

## Repo Hygiene

- `.env` and `.env.*` git-ignored
- `.env.example` fully documented in version control
- Zero hardcoded API keys or URLs in codebase

## Documentation

- [Full architecture & deployment guide](docs/DOCUMENTATION.md)
- [API reference](docs/docs.html)
- [Supabase schema](docs/supabase_schema.sql)
- [Architecture diagram](docs/architecture-complete.mmd)

---

<div align="center">

**Built by [Emir](https://github.com/ForgedEmir) · HELMo IA 2025-2026**

[![GitHub](https://img.shields.io/badge/GitHub-ForgedEmir-181717?logo=github)](https://github.com/ForgedEmir)

</div>
