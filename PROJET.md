# Oracle LoreKeeper — Fiche Projet Complète

**Projet** : Oracle LoreKeeper
**Contexte** : Projet académique — RedDragon Games / Aethelgard Online
**Objectif** : Assistant conversationnel RAG permettant aux joueurs d'interroger le lore du jeu en langage naturel, avec des réponses basées **exclusivement** sur les documents officiels.

---

## Ce que fait le projet

1. L'utilisateur pose une question via une interface web (ex. : "Qui est Lucas le Tranchant ?")
2. Le système **réécrit la question** si nécessaire pour la rendre autonome (gestion du contexte conversationnel)
3. Une **recherche sémantique** trouve les 5 passages les plus pertinents dans la base vectorielle
4. Le **LLM génère une réponse** en streaming basée uniquement sur ces passages
5. L'utilisateur peut **écouter la réponse** via synthèse vocale

---

## Architecture technique

```
Utilisateur (navigateur)
        │
        ▼
[ Interface Grimoire — HTML/CSS/JS ]
        │  POST /api/ask (SSE streaming)
        ▼
[ Flask API — main.py + routes.py ]
        │
        ├─► [ Lakera Guard + Regex ] ──► Bloque les injections
        │
        ├─► [ Supabase ] ──► Lit les 5 derniers échanges (mémoire)
        │
        ├─► [ Groq LLM ] ──► Réécrit la question si contexte nécessaire
        │
        ├─► [ Qdrant Cloud ] ──► Recherche sémantique (k=5 passages)
        │        ▲
        │        └── [ FastEmbed ] ── Embeddings multilingues
        │
        ├─► [ Groq LLM ] ──► Génère la réponse en streaming SSE
        │
        └─► [ Supabase ] ──► Sauvegarde l'échange + log monitoring
```

---

## Stack technique

| Composant | Technologie | Rôle |
|---|---|---|
| Backend | Flask 3 · Python 3.11 | Serveur web + API REST |
| LLM | Groq — `llama-3.3-70b-versatile` | Génération de réponses + réécriture |
| Base vectorielle | Qdrant Cloud | Stockage et recherche sémantique |
| Embeddings | FastEmbed (`paraphrase-multilingual-MiniLM`) | Vectorisation des documents |
| Parser de documents | Unstructured | Lecture de .md, .txt, .csv, .json, .xlsx, .xml |
| Mémoire conversationnelle | Supabase — table `conversations` | Historique multi-sessions persistant |
| Monitoring | Supabase — table `events` | Logging des questions, erreurs, latences |
| Sécurité | Lakera Guard + validation regex | Détection d'injections de prompt |
| TTS | Edge TTS — `fr-FR-HenriNeural` | Synthèse vocale en français |
| Streaming | SSE (Server-Sent Events) | Réponse token par token |
| Déploiement | Railway · Gunicorn + Gevent | Hébergement cloud |
| Rendu markdown | marked.js (CDN) | Formatage des réponses |

---

## Fonctionnalités

### Côté utilisateur
- Interface "grimoire" immersive (thème médiéval-fantastique)
- Questions en langage naturel en français
- Réponses en **streaming** (apparition token par token)
- **Synthèse vocale** de chaque réponse (bouton "Écouter")
- **Multi-conversations** : sidebar avec historique des sessions
- Chargement d'une conversation passée depuis Supabase
- Suppression d'une conversation (UI + base de données)
- Modal de conditions d'utilisation au premier lancement

### Côté système
- **Mémoire conversationnelle** : les 5 derniers échanges sont injectés dans le prompt
- **Query rewriting** : les questions de suivi ("il fait quelle taille ?") sont reformulées en questions autonomes avant la recherche
- **Sécurité double couche** : Lakera Guard (API externe) + regex locaux
- **Indexation automatique** au démarrage (détection des fichiers nouveaux/modifiés)
- **Réindexation forcée** via endpoint API
- **Dashboard monitoring** protégé par clé

### Déploiement
- Worker **Gevent** indispensable pour le streaming SSE (Gunicorn synchrone bloquerait la connexion)
- Health check endpoint `/health` pour Railway
- Variables d'environnement gérées via Railway Settings

---

## Endpoints API

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Interface grimoire |
| `POST` | `/api/ask` | Pose une question (stream SSE) |
| `POST` | `/api/reindex` | Force la réindexation Qdrant |
| `GET` | `/api/conversations` | Charge l'historique d'une session |
| `DELETE` | `/api/conversations` | Supprime une session |
| `POST` | `/api/tts` | Génère un audio MP3 (Edge TTS) |
| `GET` | `/api/monitoring/stats` | Stats de monitoring (JSON) |
| `GET` | `/monitoring` | Dashboard monitoring (HTML, protégé) |
| `GET` | `/health` | Health check Railway |

---

## Tests unitaires — 77 tests

| Fichier | Tests | Ce qui est testé |
|---|---|---|
| `test_generator.py` | 11 | Génération LLM, reformulation de questions, fallbacks |
| `test_parser.py` | 11 | Parsing de tous les formats (.md, .txt, .csv, .json, .xlsx, .xml) |
| `test_document_loader.py` | 8 | Chargement et détection des fichiers |
| `test_vector_store.py` | 8 | Ajout, suppression, recherche dans Qdrant |
| `test_tracker.py` | 9 | Lecture/écriture historique et événements Supabase |
| `test_routes.py` | 9 | Endpoints Flask, sécurité, query rewriting |
| `test_chunker.py` | 7 | Découpage des documents en chunks |
| `test_run.py` | 7 | Indexation, détection de nouveaux fichiers |
| `test_search.py` | 7 | Recherche sémantique, déduplication des sources |

**Résultat : 77/77 passed**

---

## Structure du projet

```
Oracle-LoreKeeper/
├── main.py                          # Point d'entrée Flask + CORS + health check
├── Procfile                         # Config Gunicorn/Gevent (Railway)
├── requirements.txt                 # Dépendances Python
├── data/sample/                     # Fichiers lore sources (11 fichiers)
│   ├── Lore-Lucas.txt
│   ├── artefacts.txt
│   ├── factions.md
│   ├── lieux.md
│   ├── personnages.md
│   └── ...
└── src/
    ├── api/routes.py                # Tous les endpoints REST + SSE
    ├── frontend/
    │   ├── index.html               # Interface grimoire
    │   ├── styles.css               # Thème médiéval + sidebar + TTS
    │   └── script.js                # Logique frontend (sessions, streaming, TTS)
    ├── generation/generator.py      # LLM (génération + reformulation)
    ├── ingestion/
    │   ├── document_loader.py       # Détection des fichiers à indexer
    │   ├── parser.py                # Parsing multi-format (Unstructured)
    │   ├── chunker.py               # Découpage en chunks
    │   ├── vector_store.py          # Interface Qdrant Cloud
    │   └── run.py                   # Orchestration de l'indexation
    ├── monitoring/tracker.py        # Logging Supabase + dashboard HTML
    ├── search/search.py             # Recherche sémantique Qdrant (k=5)
    ├── security/validator.py        # Lakera Guard + regex anti-injection
    ├── tts/tts.py                   # Edge TTS Henri Neural (fr-FR)
    └── test-unitaires/              # 77 tests pytest
```

---

## Variables d'environnement requises

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Clé API Groq (`gsk_...`) |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` |
| `QDRANT_URL` | URL du cluster Qdrant Cloud |
| `QDRANT_API_KEY` | Clé Qdrant Cloud |
| `SUPABASE_URL` | URL du projet Supabase |
| `SUPABASE_KEY` | Clé anon Supabase |
| `MONITORING_KEY` | Mot de passe dashboard `/monitoring` |
| `LAKERA_API_KEY` | Clé Lakera Guard |
| `PARSER` | `unstructured` |

---

## Choix techniques notables

**Pourquoi Groq ?**
API OpenAI-compatible avec des modèles open-source (Llama) très rapides. Plan gratuit généreux pour un projet académique.

**Pourquoi Qdrant Cloud ?**
Base vectorielle managée, performante, avec un plan gratuit. Évite de gérer une base locale sur Railway.

**Pourquoi Supabase pour la mémoire ?**
Persistance des conversations entre sessions sans système d'authentification. PostgreSQL managé, plan gratuit suffisant.

**Pourquoi Gevent ?**
Les workers Gunicorn synchrones bloquent sur les connexions SSE longues. Gevent permet des milliers de connexions concurrentes légères.

**Pourquoi le query rewriting ?**
Sans réécriture, la question "il fait quelle taille ?" envoyée à Qdrant ne trouve aucun résultat pertinent. Le LLM la reformule d'abord en "Quelle est la taille de Lucas le Tranchant ?" avant la recherche.

**Pourquoi Edge TTS plutôt que Kokoro/KittenTTS ?**
- KittenTTS V0.8 : ONNX 25MB, CPU, mais anglais uniquement → rejeté
- Kokoro (VPS) : accent anglais sur texte français → rejeté
- Edge TTS Henri Neural : voix française naturelle, grave, aucune dépendance système → retenu

---

*Branche active : `Emir` — Déployé sur Railway*
