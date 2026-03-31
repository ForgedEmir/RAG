# Oracle LoreKeeper

Assistant conversationnel RAG pour le lore du jeu **Aethelgard Online**.
Les joueurs posent leurs questions en langage naturel et reçoivent des réponses basées **exclusivement** sur les documents officiels — rien n'est inventé.

---

## Pipeline RAG

```
Question utilisateur
    ↓ Validation sécurité (regex + Lakera)
    ↓ Reformulation (contexte conversationnel)
    ↓ Recherche hybride : BGE-M3 (Qdrant) + BM25 → RRF
    ↓ Reranking cross-encoder (questions complexes)
    ↓ LLM avec mémoire court-terme + résumé long-terme
    ↓ Réponse streamée (SSE)
```

---

## Stack

| Composant | Technologie |
|---|---|
| Backend | FastAPI · Uvicorn · Python 3.11 |
| LLM principal | Configurable — Groq Llama 3.3 70B / DeepSeek |
| LLM fallback | Configurable — Groq Llama 4 Scout 17B |
| Embeddings | `BAAI/bge-m3` (1024 dim, local) |
| Base vectorielle | Qdrant Cloud (ou local via Docker) |
| Recherche lexicale | BM25 (rank-bm25, local) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` (local) |
| Mémoire session | Supabase — `conversations` + `messages` |
| Résumé long-terme | Supabase — `user_memory` |
| Mémoire vectorielle | Qdrant — `user_memories` (optionnel) |
| Auth utilisateur | Supabase Auth — JWT Bearer |
| Monitoring | Supabase — `events` + dashboard `/monitoring.html` |
| Observabilité LLM | Langfuse — traces, latences, coûts |
| Sécurité | Lakera Guard + regex anti-injection |
| Rate limiting | SlowAPI (Redis en prod, mémoire en dev) |
| TTS | Edge TTS — `fr-FR-HenriNeural` |
| Déploiement | Coolify · DigitalOcean · Gunicorn + UvicornWorker |

---

## Installation

```bash
git clone <url>
cd Oracle-LoreKeeper

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
cp .env.example .env
# Remplir les variables dans .env
```

---

## Configuration

### Variables essentielles

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Clé API LLM (Groq : `gsk_...`, DeepSeek, etc.) |
| `LLM_BASE_URL` | URL de l'API LLM |
| `LLM_MODEL` | Modèle principal |
| `QDRANT_URL` | URL cluster Qdrant Cloud (avec `:6333`) |
| `QDRANT_API_KEY` | Clé Qdrant Cloud |
| `SUPABASE_URL` | URL projet Supabase |
| `SUPABASE_KEY` | Clé **service_role** Supabase (pas anon) |
| `MONITORING_KEY` | Mot de passe dashboard `/monitoring` |

### Variables production

| Variable | Description | Défaut |
|---|---|---|
| `REDIS_URL` | Redis partagé (multi-workers) | `memory://` (dev) |
| `ALLOWED_ORIGINS` | CORS origins autorisées (ex : `https://mondomaine.com`) | `*` |
| `LANGFUSE_PUBLIC_KEY` | Clé publique Langfuse | — |
| `LANGFUSE_SECRET_KEY` | Clé secrète Langfuse | — |
| `LANGFUSE_HOST` | URL Langfuse | `https://cloud.langfuse.com` |
| `SENTRY_DSN` | Sentry error tracking | — |

### Variables optionnelles

| Variable | Description | Défaut |
|---|---|---|
| `RERANKER_ENABLED` | Cross-encoder actif | `true` |
| `VECTOR_MEMORY_ENABLED` | Mémoire vectorielle utilisateur | `false` |
| `QUERY_EXPANSION_ENABLED` | Génère 2 variantes de requête via LLM | `false` |
| `CONVERSATION_DEPTH` | Échanges injectés dans le contexte | `5` |
| `SUMMARY_UPDATE_INTERVAL` | Fréquence MAJ résumé (nb d'échanges) | `5` |
| `SEARCH_CACHE_TTL` | Durée cache recherche (secondes) | `300` |
| `LAKERA_API_KEY` | Détection injection IA (Lakera Guard) | — |

---

## Schéma Supabase

Exécuter dans l'éditeur SQL Supabase :

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
    role            text   not null,   -- 'user' | 'assistant'
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

-- Désactiver RLS (utiliser la clé service_role)
ALTER TABLE conversations DISABLE ROW LEVEL SECURITY;
ALTER TABLE messages      DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_memory   DISABLE ROW LEVEL SECURITY;
ALTER TABLE events        DISABLE ROW LEVEL SECURITY;

-- Index performance
CREATE INDEX ON conversations (session_id);
CREATE INDEX ON messages (conversation_id, created_at);
CREATE INDEX ON messages (user_id, role);
```

---

## Lancer l'application

### Développement
```bash
python main.py
```

### Production (Coolify / VPS)
```bash
# Gunicorn avec UvicornWorker pour FastAPI + streaming SSE
gunicorn main:app -k uvicorn.workers.UvicornWorker --workers 2 --timeout 120 --bind 0.0.0.0:8000
```

> **Important** : avec plusieurs workers, configurer `REDIS_URL` pour que le rate limiter soit partagé.

| URL | Description |
|---|---|
| `http://localhost:8080` | Interface grimoire (dev local) |
| `http://localhost:8080/monitoring.html` | Dashboard monitoring |
| `http://localhost:8080/health` | Health check JSON |

---

## Ajouter du lore

Déposer les fichiers dans `data/sample/`.
Formats : `.md` `.txt` `.csv` `.xlsx` `.xml` `.pdf`

L'indexation est automatique au démarrage. Pour forcer :
```bash
# Via le bouton "Force Reindex" dans le dashboard
# Ou via API :
curl -X POST http://localhost:8080/api/reindex -H "Content-Type: application/json" -d '{"force": true}'
```

---

## Tests

```bash
source venv/Scripts/activate   # Windows
pytest src/test-unitaires/ -v
```

Couverture : routes API, pipeline RAG, BM25, router, tracker Supabase, génération LLM, indexation.

---

## Déploiement Coolify

1. Créer un nouveau service **Docker** dans Coolify et connecter le dépôt Git
2. Coolify utilise le `Dockerfile` automatiquement (port 8000)
3. Ajouter les variables d'environnement dans **Environment Variables** :
   - Toutes les variables essentielles + production du tableau ci-dessus
   - `REDIS_URL` : ajouter un service Redis dans Coolify et copier l'URL interne générée
   - `QDRANT_URL` : URL de ton cluster Qdrant Cloud (ou service Qdrant interne Coolify)
4. Le health check est configuré dans le `Dockerfile` (`/health`, start-period 120s)
5. Pousser sur la branche principale pour déclencher un redéploiement automatique

> **Note** : `QDRANT_API_KEY` est optionnelle — si tu utilises un serveur Qdrant local sans auth, laisser vide.

---

## Structure

```
Oracle-LoreKeeper/
├── main.py                        # Entrée FastAPI, health check, logs
├── Procfile                       # Config Gunicorn (Coolify / VPS)
├── requirements.txt
├── Schéma/                        # Diagramme architecture (draw.io)
├── data/sample/                   # Fichiers lore sources
└── src/
    ├── api/
    │   ├── routes.py              # Endpoints /api/ask, /api/reindex, /api/conversations
    │   ├── auth.py                # Vérification clé monitoring
    │   ├── limiter.py             # Rate limiter (Redis ou mémoire)
    │   └── blueprints/            # Admin, media, monitoring
    ├── frontend/                  # Interface HTML/CSS/JS
    ├── generation/generator.py    # LLM, streaming, résumé, reformulation
    ├── ingestion/                 # Parser, chunker, indexation Qdrant
    ├── memory/vector_memory.py    # Mémoire vectorielle utilisateur
    ├── monitoring/tracker.py      # Supabase : events, conversations, résumé
    ├── search/search.py           # Pipeline RAG hybride
    ├── security/validator.py      # Lakera + regex
    ├── tts/                       # Edge TTS
    └── test-unitaires/            # Tests pytest
```
