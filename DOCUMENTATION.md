# Documentation Technique - Oracle LoreKeeper

## 1. Objectif

Ce projet fournit un backend RAG robuste pour du lore de jeu:

- reponses fiables basees sur des sources,
- latence maitrisee,
- configuration simple pour la production,
- capacite multi-utilisateurs.

Le mode de fonctionnement recommande est maintenant un pipeline unique et propre autour de `/api/ask`.

## 2. Composants

- API: FastAPI + Gunicorn/Uvicorn.
- Retrieval: Qdrant (vectoriel) + BM25 (lexical).
- Embeddings: FastEmbed ONNX (sans torch).
- Reranker: FastEmbed cross-encoder ONNX (optionnel/smart).
- Session + auth + event store: Supabase.
- Cache + rate-limit partage: Redis.
- Frontend: React servi en statique.

## 3. Flux d'une requete `/api/ask`

1. Auth utilisateur (JWT Supabase ou guest local en dev).
2. Masquage PII + validation securite.
3. Cache semantique (si hit, retour direct).
4. Chargement contexte utilisateur (history, summary, memories) en parallele.
5. Reformulation (si active).
6. Recherche hybride:
   - vector search (Qdrant),
   - BM25 fallback si signal vectoriel faible,
   - fusion RRF.
7. Smart rerank (selon complexite/scores).
8. HyDE fallback (si active et score trop faible).
9. Generation LLM en streaming SSE.
10. Persistance conversation + tracking + cache.

## 4. Simplifications appliquees

- Suppression de la route alternative agent (`/api/ask_agent`) et du module associe.
- Suppression du controle runtime mutable des switches search.
- Endpoint monitoring des switches conserve en lecture seule (`/api/monitoring/search-switches`).
- Pipeline principal plus lisible et surface API reduite.

## 5. Concurrence et scaling (objectif 15 users)

### 5.1 Valeurs de depart conseillees

```env
WEB_CONCURRENCY=2
BACKGROUND_MAX_WORKERS=16
GUNICORN_TIMEOUT=120
GUNICORN_GRACEFUL_TIMEOUT=30
GUNICORN_KEEPALIVE=10
REDIS_URL=redis://...
RAG_PROFILE=balanced
```

### 5.2 Pourquoi cette base

- 2 workers est souvent le meilleur compromis RAM/throughput pour des modeles locaux ONNX.
- Le threadpool interne gere les taches blocantes (DB, post-processing).
- Le rate-limit est scope par utilisateur (fingerprint JWT / guest id), pas seulement par IP.

### 5.3 Strategie d'iteration

1. Demarrer avec 2 workers.
2. Mesurer p50/p95 de `/api/ask`.
3. Si CPU libre et RAM suffisante, tester 3 workers.
4. Garder la config avec meilleure p95 stable.

## 6. Embeddings: rapide et sans torch

### 6.1 Defaut actuel

`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

- Multilingue.
- 384 dimensions.
- Tres rapide pour ingestion/recherche.

### 6.2 Alternative qualite

`intfloat/multilingual-e5-large`

- Qualite semantique plus elevee sur cas difficiles.
- Plus lent et plus couteux en RAM/CPU.
- 1024 dimensions.

### 6.3 Bonnes pratiques

- Changer de modele implique souvent une reindexation complete.
- Garder `QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH=true` en prod pour eviter les pannes apres changement de modele.

## 7. Qdrant et dimensions

Le backend valide la dimension attendue de la collection.

Si mismatch:

- avec `QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH=true`: recreation automatique,
- sinon: erreur explicite pour eviter de servir des resultats incoherents.

Variables utiles:

```env
QDRANT_VECTOR_SIZE=
QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH=true
```

## 8. Configuration RAG essentielle

```env
RAG_PROFILE=balanced
RAG_FAST_MODE=false

RERANKER_ENABLED=true
SMART_RERANK_ENABLED=true
RERANK_SIMPLE_QUERIES=false
RERANKER_MODEL=Xenova/ms-marco-MiniLM-L-6-v2
RERANKER_MAX_INPUT=4
RERANKER_TOP_N=6

QUERY_EXPANSION_ENABLED=false
HYDE_ENABLED=true
HYDE_TIMEOUT_SECONDS=3.5

SEARCH_SIMPLE_CANDIDATES=5
SEARCH_COMPLEX_CANDIDATES=14
SEARCH_FINAL_TOP_N=4
MIN_VECTOR_BEFORE_BM25=3

REFORMULATION_ENABLED=true
MAX_RESPONSE_SECONDS=10
```

## 9. Startup et warmup

Variables:

```env
STARTUP_INDEX_ENABLED=true
STARTUP_WARMUP_ENABLED=true
WATCHDOG_ENABLED=true
```

Comportement:

- warmup embeddings/reranker/LLM pour eviter la latence a froid,
- indexation initiale et reindex auto via watchdog (si active).

## 10. Coolify: checklist de deployment

1. Service Docker connecte au repo.
2. Ajouter Redis managé ou service Redis Coolify.
3. Configurer variables `.env` (sans commiter de secrets).
4. Verifier `ALLOWED_ORIGINS` avec votre domaine.
5. Verifier healthcheck `GET /health`.
6. Lancer tests avant push production.

## 11. Hygiene repo et securite

- `.env` et `.env.*` ignores par git.
- `.env.example` versionne.
- Rotation des cles recommandee si une cle a deja ete exposee hors environnement prive.

## 12. Endpoints utiles

- `GET /health`
- `POST /api/ask`
- `POST /api/feedback`
- `POST /api/reindex`
- `GET /api/monitoring/pipeline`
- `GET /api/monitoring/features`
- `GET /api/monitoring/search-switches` (read-only)
- `GET /api/cache/stats`

## 13. Tests

Commande standard:

```bash
python -m pytest src/test-unitaires -q
```

Commande rapide apres modifications retrieval/routes:

```bash
python -m pytest src/test-unitaires/test_search.py src/test-unitaires/test_routes.py -q
```

## 14. Troubleshooting rapide

### 14.1 Reponses lentes

- Desactiver features couteuses non essentielles (`QUERY_EXPANSION_ENABLED=false`).
- Limiter reranker (`RERANKER_MAX_INPUT=4`).
- Verifier warmup actif (`STARTUP_WARMUP_ENABLED=true`).
- Verifier latence fournisseur LLM.

### 14.2 Erreurs dimension Qdrant

- Verifier `EMBEDDING_MODEL` et `QDRANT_VECTOR_SIZE`.
- Laisser auto-recreate actif pour remediation automatique.
- Reindexer apres changement de modele.

### 14.3 Saturation sous charge

- Verifier Redis actif.
- Augmenter prudemment `WEB_CONCURRENCY` (2 -> 3).
- Surveiller RAM et p95.

## 15. Fichiers cles

- `main.py`: startup, warmup, app wiring.
- `src/api/routes.py`: endpoint `/api/ask`, streaming, persistence.
- `src/search/search.py`: retrieval hybride et smart rerank.
- `src/ingestion/vector_store.py`: Qdrant client + validation dimensions.
- `start.sh`: process model API + MCP.
- `README.md`: guide operationnel court.
