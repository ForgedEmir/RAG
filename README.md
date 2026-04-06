# :crystal_ball: HELMo Oracle

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![LangChain](https://img.shields.io/badge/LangChain-RAG-green)
![Docker](https://img.shields.io/badge/Docker-20.10-2496ED?logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-Proprietary-red)

> Assistant conversationnel RAG pour le lore du jeu **Aethelgard Online**.
> Les joueurs posent leurs questions en langage naturel et recoivent des reponses basees **exclusivement** sur les documents officiels — rien n'est invente.

---

## Pipeline RAG

```
Question utilisateur
    | Validation securite (regex + Lakera Guard)
    | Masquage PII (emails, telephones)
    | Cache semantique (Redis, similarite > 92%)
    | Reformulation contextuelle (LLM + historique)
    | Recherche hybride : BGE-M3 (Qdrant) + BM25 → fusion RRF
    | Reranking cross-encoder ONNX (questions complexes)
    | Generation LLM avec memoire court-terme + resume long-terme
    v Reponse streamee (Server-Sent Events)
```

---

## Stack

| Composant | Technologie |
|---|---|
| Backend | FastAPI, Uvicorn, Python 3.12 |
| Frontend | React 19, Tailwind CSS 4, Vite 8, Framer Motion |
| LLM | Groq Llama 3.3 70B (principal) + fallback multi-tier |
| Embeddings | `BAAI/bge-m3` 1024 dim (FastEmbed, local ONNX) |
| Reranker | `BAAI/bge-reranker-base` (cross-encoder, local ONNX) |
| Base vectorielle | Qdrant Cloud |
| Recherche lexicale | BM25 (rank-bm25, local) |
| Auth | Supabase Auth (JWT, GitHub OAuth, Google OAuth) |
| Sessions + monitoring | Supabase PostgreSQL |
| Cache | Redis (recherche + semantique + rate limit) |
| Observabilite LLM | Langfuse (traces, latences, evaluateurs) |
| Securite | Lakera Guard + regex anti-injection + PII masking |
| TTS / STT | Edge TTS / Whisper (Groq) |
| MCP | Stdio (Claude Desktop) + SSE (Claude.ai, Cursor) |
| Deploiement | Docker, Gunicorn, Coolify |

---

## Features

- **Recherche hybride** — vectorielle + BM25 + fusion RRF + reranking cross-encoder
- **Cache intelligent** — Redis TTL (recherche) + cache semantique (reponses LLM)
- **HyDE fallback** — generation de documents hypothetiques si scores trop bas
- **Reformulation** — reecrit les questions vagues via le contexte conversationnel
- **Memoire 3 niveaux** — court-terme (5 echanges) + resume long-terme + memoire vectorielle
- **Streaming SSE** — reponses token par token en temps reel
- **Fallback LLM 4 tiers** — toujours une reponse, meme si le provider principal tombe
- **Securite 3 couches** — whitelist lore + regex + Lakera Guard ML
- **Human-in-the-loop** — feedback pouce haut/bas + LLM-as-a-Judge
- **Evaluateurs Langfuse** — Hallucination, Context Relevance, Correctness
- **TTS/STT** — lecture audio des reponses + dictee vocale
- **Agent ReAct** — boucle pensee/action/observation alternative au RAG direct
- **Serveur MCP** — connecte a Claude Desktop, Cursor, Claude.ai
- **Monitoring dashboard** — stats, pipeline, logs, upload drag & drop
- **Watchdog** — reindexation automatique quand les fichiers changent

---

## Installation

```bash
git clone <url>
cd Oracle-LoreKeeper

python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
cp .env.example .env
# Remplir les variables dans .env
```

### Frontend React

```bash
cd src/frontend-react
npm install
npm run build
cd ../..
```

---

## Configuration

### Variables essentielles

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Cle API LLM (Groq : `gsk_...`, OpenRouter : `sk-or-...`) |
| `LLM_BASE_URL` | URL API LLM (`https://api.groq.com/openai/v1`) |
| `LLM_MODEL` | Modele principal (`llama-3.3-70b-versatile`) |
| `QDRANT_URL` | URL cluster Qdrant (avec `:6333`) |
| `QDRANT_API_KEY` | Cle Qdrant Cloud |
| `SUPABASE_URL` | URL projet Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Cle **service_role** Supabase |
| `SUPABASE_ANON_KEY` | Cle **anon** Supabase (pour le frontend) |
| `MONITORING_KEY` | Mot de passe dashboard monitoring |

### Variables production

| Variable | Description | Defaut |
|---|---|---|
| `REDIS_URL` | Redis partage (multi-workers) | memoire locale |
| `FALLBACK_API_KEY` | Cle LLM fallback | — |
| `FALLBACK_MODEL` | Modele fallback | `llama-3.1-8b-instant` |
| `ALLOWED_ORIGINS` | CORS (domaine Coolify) | `*` |
| `LAKERA_API_KEY` | Lakera Guard (anti-injection ML) | — |
| `LANGFUSE_PUBLIC_KEY` / `SECRET_KEY` | Observabilite LLM | — |
| `SENTRY_DSN` | Error tracking | — |

### Feature flags

| Variable | Defaut | Description |
|---|---|---|
| `RERANKER_ENABLED` | `true` | Cross-encoder actif |
| `VECTOR_MEMORY_ENABLED` | `false` | Memoire vectorielle par utilisateur |
| `QUERY_EXPANSION_ENABLED` | `false` | Variantes de requete via LLM |
| `REFORMULATION_ENABLED` | `true` | Reformulation contextuelle |
| `SECURITY_VALIDATOR` | `rules` | Mode : `true` / `rules` / `shadow` / `false` |

> Voir [DOCUMENTATION.md](DOCUMENTATION.md) pour la liste complete et les explications detaillees.

---

## Schema Supabase

Executer dans l'editeur SQL Supabase :

```sql
CREATE TABLE conversations (
    id         bigint generated always as identity primary key,
    session_id uuid        not null,
    user_id    uuid        not null,
    created_at timestamptz default now()
);

CREATE TABLE messages (
    id              bigint generated always as identity primary key,
    conversation_id bigint references conversations(id) on delete cascade,
    user_id         uuid   not null,
    role            text   not null,
    content         text   not null,
    created_at      timestamptz default now()
);

CREATE TABLE user_memory (
    user_id    uuid primary key,
    summary    text,
    updated_at timestamptz default now()
);

CREATE TABLE events (
    id         bigint generated always as identity primary key,
    type       varchar,
    detail     text,
    latency_ms int4,
    created_at timestamptz default now()
);

CREATE TABLE feedback (
    id          bigint generated always as identity primary key,
    session_id  uuid,
    user_id     uuid,
    rating      int4,
    comment     text default '',
    judge_score float8,
    created_at  timestamptz default now()
);

CREATE INDEX ON conversations (session_id);
CREATE INDEX ON conversations (user_id);
CREATE INDEX ON messages (conversation_id, created_at);
CREATE INDEX ON messages (user_id, role);
CREATE INDEX ON feedback (session_id);
```

---

## Lancer l'application

### Developpement

```bash
python main.py
# → http://localhost:8000
```

### Production (Docker)

```bash
docker compose up --build
# → http://localhost:8000 (API + frontend)
# → http://localhost:8001 (MCP SSE)
```

### Production (Coolify)

1. Creer un service **Docker** dans Coolify, connecter le depot Git
2. Ajouter les variables d'environnement (voir ci-dessus)
3. Ajouter un service **Redis** + **Qdrant** dans Coolify
4. Push sur la branche principale → deploiement automatique
5. Healthcheck integre (`/health`, start-period 120s)

---

## Endpoints API

| Endpoint | Methode | Auth | Description |
|---|---|---|---|
| `/health` | GET | — | Health check (LLM, Qdrant, Supabase) |
| `/api/ask` | POST | JWT | Question RAG (streaming SSE) |
| `/api/ask_agent` | POST | JWT | Question via agent ReAct |
| `/api/feedback` | POST | JWT | Feedback utilisateur (1-5) |
| `/api/conversations/list` | GET | JWT | Liste des conversations |
| `/api/conversations/messages` | GET | JWT | Messages d'une session |
| `/api/conversations` | DELETE | JWT | Supprimer une conversation |
| `/api/reindex` | POST | Key | Forcer la reindexation |
| `/api/admin/sources` | GET | Key | Liste des fichiers indexes |
| `/api/admin/upload` | POST | Key | Uploader un fichier lore |
| `/api/tts` | POST | — | Texte → audio MP3 |
| `/api/stt` | POST | — | Audio → texte |
| `/api/monitoring/stats` | GET | Key | Statistiques globales |
| `/api/cache/stats` | GET | Key | Stats du cache semantique |

---

## Ajouter du lore

Deposer les fichiers dans `data/sample/`.
Formats supportes : `.md` `.txt` `.csv` `.xlsx` `.xml` `.json` `.pdf`

L'indexation est automatique au demarrage et via watchdog. Pour forcer :

```bash
curl -X POST http://localhost:8000/api/reindex \
  -H "Content-Type: application/json" \
  -H "X-Monitoring-Key: votre_cle" \
  -d '{"force": true}'
```

---

## Tests

```bash
python -m pytest src/test-unitaires/ -v
```

**49/49 tests passed** — couverture : routes API, pipeline RAG, BM25, reranker, tracker Supabase, generation LLM, ingestion, securite, feedback, PII masking.

---

## Structure

```
Oracle-LoreKeeper/
├── main.py                          # Entree FastAPI + SPA fallback
├── mcp_server.py                    # Serveur MCP (stdio + SSE)
├── start.sh                         # Entrypoint Docker (API + MCP)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── supabase_schema.sql
├── data/sample/                     # Fichiers lore sources
└── src/
    ├── api/
    │   ├── routes.py                # /api/ask, /api/feedback, /api/reindex
    │   ├── auth.py                  # JWT Supabase + guest mode
    │   ├── limiter.py               # Rate limiting (Redis)
    │   └── blueprints/
    │       ├── admin.py             # Upload, sources, evaluation
    │       ├── media.py             # TTS, STT
    │       └── monitoring_bp.py     # Stats, pipeline, reformulation
    ├── frontend-react/              # React 19 + Tailwind + Vite
    │   └── src/
    │       ├── App.jsx              # Auth (login, signup, OAuth)
    │       ├── ChatPage.jsx         # Interface chat + streaming
    │       ├── MonitoringPage.jsx   # Dashboard monitoring
    │       ├── useChat.js           # Hook gestion sessions/messages
    │       └── auth.js              # Supabase SDK wrapper
    ├── generation/generator.py      # LLM streaming + fallback + reformulation
    ├── search/search.py             # Pipeline hybride + cache Redis
    ├── ingestion/
    │   ├── run.py                   # Orchestrateur indexation
    │   ├── chunker.py               # Decoupage en chunks
    │   ├── parser.py                # Parsing multi-format
    │   ├── vector_store.py          # Interface Qdrant
    │   └── watcher.py               # Watchdog auto-reindex
    ├── retrieval/hyde.py            # HyDE fallback
    ├── agent/react_agent.py         # Agent ReAct
    ├── caching/semantic_cache.py    # Cache semantique (Redis)
    ├── memory/vector_memory.py      # Memoire vectorielle utilisateur
    ├── monitoring/tracker.py        # Events + sessions Supabase
    ├── security/
    │   ├── validator.py             # Regex + Lakera Guard
    │   ├── pii_masker.py            # Masquage PII
    │   └── judge.py                 # LLM-as-a-Judge
    ├── evaluation/ragas_eval.py     # RAGAS metrics
    ├── tts/tts.py                   # Edge TTS
    └── test-unitaires/              # 49 tests pytest
```

---

## Documentation complete

Voir **[DOCUMENTATION.md](DOCUMENTATION.md)** pour l'explication detaillee de chaque feature, avec des exemples, les schemas d'architecture, les metriques de performance, et la configuration complete.

---

## Equipe

| | Nom |
|---|---|
| :bust_in_silhouette: | **Emir** |
| :bust_in_silhouette: | **Nicolas** |
| :bust_in_silhouette: | **Ediz** |
| :bust_in_silhouette: | **Tom** |

---

*HELMo — Avril 2026*
