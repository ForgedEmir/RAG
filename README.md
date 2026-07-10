<div align="center">

# RAG — Accounting Intelligence 📊

### Production-grade RAG for accounting professionals

[![Python](https://img.shields.io/badge/Python-3.11+-1e3a5f?logo=python&logoColor=white&style=for-the-badge)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white&style=for-the-badge)](https://fastapi.tiangolo.com)
[![Qdrant](https://img.shields.io/badge/Vector_DB-Qdrant-EA4335?style=for-the-badge)](https://qdrant.tech)
[![Cerebras](https://img.shields.io/badge/LLM-Cerebras-FF6B35?style=for-the-badge)](https://cerebras.ai)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white&style=for-the-badge)](https://docker.com)
[![MCP](https://img.shields.io/badge/MCP-Protocol-7C3AED?style=for-the-badge)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-cc8a3d?style=for-the-badge)](LICENSE)

`#rag` `#accounting` `#tax` `#fastapi` `#qdrant` `#cerebras` `#mcp` `#ai`

*No PyTorch · No GPU needed · Config-driven · Traceable pipeline*

</div>

---

## Overview

A production-grade **Retrieval-Augmented Generation (RAG)** engine built for accounting professionals. Ask a question about tax legislation, accounting standards, or Peppol compliance — the system searches your indexed documents and streams a sourced answer in real time.

**Why accounting?**

| Problem | Solution |
|---|---|
| LLMs hallucinate answers on fiscal law | Hybrid retrieval (vector + BM25) + reranking + source citations |
| Slow responses break workflow | Cerebras inference (~500ms) + Redis semantic cache + SSE streaming |
| Regulations change yearly (Peppol, VAT, etc.) | Re-index on demand, no fine-tuning |
| Multiple clients, multiple files | User memory summaries + session history + Supabase auth |
| Production reliability | Rate limiting, PII masking, monitoring dashboard |

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│   Client     │     │                  RAG Engine                   │
│  (React /   │────▶│                                              │
│   API)       │     │  POST /api/ask → Auth → PII → Security      │
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
| **Vector DB** | Qdrant | Cloud-native, fast, great filtering |
| **Embeddings** | FastEmbed ONNX (MiniLM 384d) | No GPU, no PyTorch, 5ms inference |
| **Reranker** | FastEmbed ONNX (cross-encoder) | Conditional activation — smart rerank |
| **Lexical** | BM25 (rank-bm25) | French stopwords, recovers vector misses |
| **LLM** | Cerebras (llama3.1-8b) / Groq fallback | ~500ms inference, auto-failover |
| **Auth** | Supabase (PostgreSQL + JWT) | Serverless, row-level security |
| **Cache** | Redis + SlowAPI | Semantic cache + rate limiting |
| **Security** | Lakera Guard + regex PII mask | Injection detection, GDPR compliance |
| **Frontend** | React + Vite + Tailwind | Static, served by FastAPI |
| **Monitoring** | Langfuse | LLM-as-Judge, full trace → eval score |
| **Integration** | MCP Server (stdio/SSE) | Claude Desktop, Cursor, any MCP client |
| **Deploy** | Docker + Coolify | 2-command startup, zero-downtime |

---

## Quickstart

### Requirements

- Python 3.11+, Node.js 18+, Docker (optional)

```bash
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

## API Endpoints

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/ask` | POST | JWT/guest | **Main RAG endpoint** — SSE stream |
| `/api/feedback/vote` | POST | JWT/guest | Thumbs up/down by trace_id |
| `/api/conversations` | GET/DELETE | JWT/guest | Session conversation history |
| `/api/monitoring/stats` | GET | monitoring key | Global usage & pipeline health |
| `/api/cache/stats` | GET | monitoring key | Semantic cache hit rates |
| `/api/admin/sources` | GET | monitoring key | Indexed source files |
| `/health` | GET | — | Component health check |
| *+ 9 more* | | | See full docs |

**Request:**
```json
POST /api/ask
{
  "question": "What is the VAT rate for renovation work in Belgium?",
  "session_id": "uuid-v4",
  "user_id": "accountant_uuid"
}
```

**Response:** Server-Sent Events
```
data: {"type": "text", "text": "The reduced VAT rate of 6% applies to renovation..."}
data: {"type": "done", "trace_id": "...", "model": "llama3.1-8b"}
```

---

## Accounting use cases

| Domain | Example question |
|---|---|
| **VAT** | "What rate applies to catering in Belgium?" |
| **Peppol** | "Which businesses are affected by the Peppol mandate in 2026?" |
| **Social** | "What is the 2026 self-employed income cap?" |
| **Tax** | "How do I declare capital gains on share sales?" |
| **Accounting** | "What are the depreciation rules for fixed assets?" |
| **GDPR** | "What mandatory information must appear on a B2B invoice?" |

---

## Key design decisions

- **No PyTorch runtime** → All embeddings/reranking via ONNX (FastEmbed). Small Docker image, no GPU.
- **Config-driven** → Every provider, model and feature flag is an env var. No hardcoded secrets.
- **HyDE + BM25 fallbacks** → If vector retrieval score is weak, it tries hypothetical document embeddings and lexical search before giving up.
- **Smart rerank** → Cross-encoder only activates when the top-1 vector score is below threshold. Saves latency when the primary result is already good.
- **Single answer pipeline** → One endpoint (`/api/ask`) does everything. Simple to integrate, simple to monitor.

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

## MCP integration

Claude Desktop, Cursor, or any MCP client can query the system directly.

```json
{
  "mcpServers": {
    "rag-accounting": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "LLM_API_KEY": "...",
        "QDRANT_URL": "...",
        "QDRANT_API_KEY": "..."
      }
    }
  }
}
```

---

## Production profile

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

## Documentation

- [Architecture & deployment guide](docs/DOCUMENTATION.md)
- [API reference](docs/docs.html)
- [Supabase schema](docs/supabase_schema.sql)
- [Architecture diagram](docs/architecture-complete.mmd)

---

## Contributing

| Resource | Description |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | Setup, workflow, PR process |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Community standards |
| [SECURITY.md](SECURITY.md) | Vulnerability reporting |
| [LICENSE](LICENSE) | MIT — free to use, modify, distribute |

---

<div align="center">

**RAG** — Production-grade retrieval-augmented generation for accounting.

[![GitHub](https://img.shields.io/badge/GitHub-ForgedEmir-181717?logo=github)](https://github.com/ForgedEmir)

</div>
