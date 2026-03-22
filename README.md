# Oracle LoreKeeper

> Assistant conversationnel RAG pour le lore du jeu **Aethelgard Online**.
> Les joueurs posent leurs questions en langage naturel et reçoivent des réponses basées **exclusivement** sur les documents officiels du jeu — rien n'est inventé.

---

## Comment ça fonctionne

```
Question utilisateur
        ↓
  Réécriture de la question (contexte conversationnel)
        ↓
  Recherche sémantique dans Qdrant (k=5 passages)
        ↓
  Génération LLM (Groq / Llama 3.3 70B)
        ↓
  Réponse en streaming SSE → Interface grimoire
```

1. **Sécurité** — Lakera Guard + regex filtrent les injections avant tout traitement
2. **Mémoire** — Les 5 derniers échanges de la session sont injectés dans le prompt
3. **Réécriture** — Les questions de suivi ("il fait quelle taille ?") sont reformulées en questions autonomes avant la recherche
4. **TTS** — Chaque réponse peut être écoutée via Edge TTS (voix Henri, fr-FR)

---

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Flask 3 · Python 3.11 |
| LLM | Groq — `llama-3.3-70b-versatile` |
| Base vectorielle | Qdrant Cloud |
| Embeddings | FastEmbed (`paraphrase-multilingual-MiniLM`) |
| Parser de documents | Unstructured |
| Mémoire conversationnelle | Supabase — table `conversations` |
| Monitoring | Supabase — table `events` · dashboard `/monitoring` |
| Sécurité | Lakera Guard + validation regex |
| TTS | Edge TTS — `fr-FR-HenriNeural` |
| Streaming | SSE avec Gunicorn + Gevent |
| Déploiement | Railway |

---

## Installation locale

```bash
git clone <url-du-repo>
cd Oracle-LoreKeeper

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
```

---

## Configuration

Copier le fichier d'exemple et compléter les clés :

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Clé API Groq (format `gsk_...`) |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |
| `QDRANT_URL` | URL du cluster Qdrant Cloud |
| `QDRANT_API_KEY` | Clé Qdrant Cloud |
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_KEY` | Clé anon Supabase |
| `MONITORING_KEY` | Mot de passe pour accéder au dashboard `/monitoring` |
| `LAKERA_API_KEY` | Clé Lakera Guard |
| `LAKERA_PROJECT_ID` | ID projet Lakera _(optionnel)_ |
| `PARSER` | `unstructured` _(recommandé)_ |

### Tables Supabase requises

Exécuter dans l'éditeur SQL de Supabase :

```sql
-- Historique des conversations (mémoire multi-sessions)
CREATE TABLE conversations (
    id         bigint generated always as identity primary key,
    session_id text        not null,
    question   text        not null,
    answer     text        not null,
    created_at timestamptz default now()
);
ALTER TABLE conversations DISABLE ROW LEVEL SECURITY;
CREATE INDEX ON conversations (session_id, created_at);

-- Événements de monitoring (questions, erreurs, injections, latence)
CREATE TABLE events (
    id         bigint generated always as identity primary key,
    type       varchar,
    detail     text,
    latency_ms int4,
    created_at timestamptz default now()
);
ALTER TABLE events DISABLE ROW LEVEL SECURITY;
```

---

## Ajouter du contenu lore

Placer les fichiers dans `data/sample/`.
Formats supportés : `.md` · `.txt` · `.csv` · `.json` · `.xlsx` · `.xml`

L'indexation dans Qdrant se fait **automatiquement au démarrage**.
Pour forcer une réindexation complète :

```bash
curl -X POST http://localhost:5000/api/reindex \
     -H "Content-Type: application/json" \
     -d '{"force": true}'
```

---

## Lancement

```bash
python main.py
```

| URL | Description |
|---|---|
| `http://localhost:5000` | Interface grimoire |
| `http://localhost:5000/monitoring?key=<MONITORING_KEY>` | Dashboard de monitoring |
| `http://localhost:5000/health` | Health check |

---

## Tests

```bash
pytest src/test-unitaires/ -v
```

**77 tests** couvrant : génération, reformulation, recherche, ingestion, sécurité, routes API, monitoring Supabase.

---

## Déploiement Railway

1. Connecter le dépôt Git à Railway
2. Ajouter toutes les variables d'environnement dans **Settings → Variables**
3. Railway détecte le `Procfile` et lance automatiquement :

```
gunicorn main:app --worker-class gevent --workers 2 --timeout 120
```

> Le worker **Gevent** est indispensable pour le streaming SSE — un worker synchronique bloquerait la connexion.

---

## Structure du projet

```
Oracle-LoreKeeper/
├── main.py                        # Point d'entrée Flask + CORS + health check
├── Procfile                       # Config Gunicorn (Railway)
├── requirements.txt
├── data/sample/                   # Fichiers lore sources
└── src/
    ├── api/routes.py              # Endpoints REST + SSE
    ├── frontend/                  # Interface grimoire (HTML/CSS/JS)
    ├── generation/generator.py    # LLM + reformulation de questions
    ├── ingestion/                 # Parser + chunker + indexation Qdrant
    ├── monitoring/tracker.py      # Logging Supabase + dashboard
    ├── search/search.py           # Recherche sémantique Qdrant
    ├── security/validator.py      # Lakera Guard + regex
    ├── tts/tts.py                 # Edge TTS Henri Neural
    └── test-unitaires/            # 77 tests pytest
```
