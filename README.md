# Oracle LoreKeeper

Assistant conversationnel intelligent pour le lore du jeu **Aethelgard Online**.
Les joueurs posent des questions en langage naturel et reçoivent des réponses basées exclusivement sur les documents officiels du jeu.

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Flask (Python 3.11) |
| LLM | Groq — llama-3.3-70b-versatile |
| Base vectorielle | Qdrant Cloud |
| Embeddings | FastEmbed (paraphrase-multilingual-MiniLM) |
| Parser de documents | Unstructured |
| Mémoire & monitoring | Supabase (PostgreSQL) |
| Sécurité | Lakera Guard + Regex |
| TTS | Edge TTS — Henri Neural (fr-FR) |
| Déploiement | Railway (Gunicorn + Gevent) |

---

## Prérequis

- Python 3.11
- Comptes : [Groq](https://console.groq.com), [Qdrant Cloud](https://cloud.qdrant.io), [Supabase](https://supabase.com), [Lakera](https://platform.lakera.ai)

---

## Installation

```bash
git clone <url-du-repo>
cd Oracle-LoreKeeper
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

---

## Configuration

Copier le fichier d'exemple et remplir les clés :

```bash
cp .env.example .env
```

Variables requises dans `.env` :

```env
# LLM (Groq)
OPENAI_API_KEY=gsk_...
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

# Base vectorielle (Qdrant Cloud)
QDRANT_URL=https://...qdrant.io
QDRANT_API_KEY=...

# Mémoire & monitoring (Supabase)
SUPABASE_URL=https://....supabase.co
SUPABASE_KEY=eyJ...
MONITORING_KEY=mot_de_passe_dashboard

# Sécurité (Lakera Guard)
LAKERA_API_KEY=...
LAKERA_PROJECT_ID=project-...  # optionnel

# Parser (unstructured recommandé)
PARSER=unstructured
```

### Supabase — tables requises

Exécuter dans l'éditeur SQL Supabase :

```sql
-- Événements de monitoring
CREATE TABLE events (
    id bigint generated always as identity primary key,
    type varchar,
    detail text,
    latency_ms int4,
    created_at timestamptz default now()
);
ALTER TABLE events DISABLE ROW LEVEL SECURITY;

-- Historique des conversations
CREATE TABLE conversations (
    id bigint generated always as identity primary key,
    session_id text not null,
    question text not null,
    answer text not null,
    created_at timestamptz default now()
);
ALTER TABLE conversations DISABLE ROW LEVEL SECURITY;
CREATE INDEX ON conversations (session_id, created_at);
```

---

## Ajouter du contenu lore

Placer les fichiers dans `data/sample/`. Formats supportés : `.md`, `.txt`, `.csv`, `.json`, `.xlsx`, `.xml`

L'indexation est automatique au démarrage. Pour forcer une réindexation :

```bash
curl -X POST http://localhost:5000/api/reindex -H "Content-Type: application/json" -d '{"force": true}'
```

---

## Lancement

```bash
python main.py
```

Interface accessible sur : `http://localhost:5000`
Dashboard monitoring : `http://localhost:5000/monitoring?key=<MONITORING_KEY>`

---

## Tests

```bash
pytest src/test-unitaires/ -v
```

77 tests unitaires couvrant : génération, recherche, ingestion, sécurité, routes, monitoring.

---

## Déploiement Railway

1. Connecter le dépôt Git à Railway
2. Ajouter toutes les variables d'environnement dans **Settings → Variables**
3. Railway détecte automatiquement le `Procfile` et lance Gunicorn avec Gevent

> Le endpoint `/health` est disponible pour les health checks Railway.
