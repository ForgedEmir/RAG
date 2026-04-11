# Canvas de Présentation — Oracle LoreKeeper
**Jury | 20 minutes | 4 intervenants**

---

## Objectif
Se valoriser en tant que développeurs. Montrer qu'on maîtrise les outils, les pratiques et le travail d'équipe — pas vendre un produit.

---

## Structure globale

| # | Personne | Thème | Durée |
|---|----------|-------|-------|
| 1 | **P1** | Introduction + Qu'est-ce qu'un RAG ? | 5 min |
| 2 | **P2** | Architecture & Stack technique | 5 min |
| 3 | **P3** | Fonctionnalités, Sécurité & Monitoring | 5 min |
| 4 | **P4** | Travail d'équipe, Outils & Bilan | 5 min |

---

## PARTIE 1 — Introduction + RAG (P1) | 5 min

### Slides

**Slide 1 — Accroche (30 sec)**
- "On a construit un assistant IA pour répondre aux questions des joueurs d'un MMORPG fictif."
- But : découvrir les technologies modernes du monde professionnel
- Avant de parler du projet, il faut comprendre la technologie derrière : **le RAG**

---

**Slide 2 — Le problème des LLMs (1 min)**

> *"Les LLMs sont puissants, mais ils ont deux gros problèmes."*

1. **Hallucination** : ils inventent des réponses plausibles mais fausses
2. **Données figées** : leur connaissance s'arrête à une date (cutoff)
3. **Pas d'accès à vos données privées** : ils ne connaissent pas votre base documentaire

→ *"Comment intégrer un LLM dans un système réel avec des données qu'on contrôle ?"*

---

**Slide 3 — La solution : RAG (2 min)**

**RAG = Retrieval-Augmented Generation**

Schéma simple à montrer :

```
Question utilisateur
       ↓
[RETRIEVE] → Chercher les passages pertinents dans la base documentaire
       ↓
[AUGMENT]  → Injecter ces passages dans le prompt du LLM
       ↓
[GENERATE] → Le LLM répond en se basant sur les vrais documents
       ↓
Réponse sourcée et fiable
```

Avantages clés :
- Les réponses sont **ancrées dans les documents réels**
- On peut **mettre à jour la base** sans ré-entraîner le modèle
- On garde le **contrôle sur les données**

*Analogie : "C'est comme donner à un assistant un livre de référence avant de lui poser une question, plutôt que de lui demander de deviner."*

---

**Slide 4 — Notre cas d'usage (1 min 30)**

- Projet : **Oracle LoreKeeper** — assistant lore pour un MMORPG
- Les joueurs posent des questions sur l'univers du jeu (personnages, lieux, factions…)
- Nos documents : fichiers Markdown, CSV, PDF, XML, TXT

*Transition : "Maintenant que vous comprenez le RAG, voici comment on l'a implémenté."*

---

## PARTIE 2 — Architecture & Stack (P2) | 5 min

### Slides

**Slide 5 — Vue d'ensemble de l'architecture (1 min 30)**

Montrer un schéma du pipeline complet :

```
Documents (MD, PDF, CSV...)
       ↓
[INGESTION] Parsing → Chunking → Embedding
       ↓
[QDRANT] Base vectorielle (cloud)
       ↓                        ↑
[REQUÊTE] Question utilisateur  |
       ↓                        |
[RECHERCHE HYBRIDE]             |
  • Vectorielle (FastEmbed)     |
  • BM25 (lexicale)             |
  • Fusion RRF                  |
  • Reranking cross-encoder     |
       ↓
[LLM] Cerebras (llama3.1-8b) → fallback Groq
       ↓
[API FastAPI] → SSE streaming → Frontend React
```

---

**Slide 6 — Stack technique (2 min)**

Présenter par couche :

| Couche | Technologies |
|--------|-------------|
| **API** | FastAPI, Uvicorn, Gunicorn (4 workers) |
| **Frontend** | React 19, Vite, Tailwind CSS |
| **Recherche** | Qdrant, FastEmbed ONNX, BM25, RRF |
| **LLM** | Cerebras (primaire) + Groq (fallback) |
| **Cache** | Redis (sémantique, 92% seuil de similarité) |
| **Auth & BDD** | Supabase (JWT + PostgreSQL) |
| **Infra** | Docker, docker-compose |

Point fort à souligner : **"On a choisi FastEmbed ONNX pour ne pas dépendre de PyTorch — les embeddings tournent sans GPU, ce qui simplifie le déploiement."**

---

**Slide 7 — Recherche hybride (1 min)**

*"C'est ici qu'on va au-delà d'un RAG basique."*

- **Vectorielle** : comprend le sens sémantique
- **BM25** : précis sur les termes exacts (noms propres, termes techniques)
- **RRF** (Reciprocal Rank Fusion) : combine les deux classements
- **Reranker** (cross-encoder) : re-classe les résultats finaux par pertinence réelle
- **HyDE** (fallback) : si pas de résultats → le LLM génère un document hypothétique pour la recherche

*"Un RAG simple fait juste de la recherche vectorielle. On a empilé plusieurs niveaux pour améliorer la qualité des résultats."*

---

**Slide 8 — LLM + Cache sémantique (30 sec)**

- **Streaming SSE** : la réponse s'affiche mot par mot (meilleure UX)
- **Cache Redis** : si deux questions ont 92%+ de similarité sémantique → on renvoie la réponse cached directement
- **Fallback automatique** : si Cerebras est down → bascule sur Groq en transparence

---

## PARTIE 3 — Features, Sécurité & Monitoring (P3) | 5 min

### Slides

**Slide 9 — Fonctionnalités clés (1 min 30)**

*"On n'a pas juste branché une API LLM. On a construit un vrai système."*

- **Multi-utilisateurs** : sessions séparées, historique de conversation (5 derniers échanges)
- **Résumés utilisateur** : le LLM génère un profil de 150 mots par user pour personnaliser les réponses
- **Rate limiting** : SlowAPI + Redis, par user ID — protection contre l'abus
- **Profils d'exécution** : `fast` / `balanced` / `quality` — ajustable selon les besoins
- **Reformulation de requête** : les questions ambiguës sont réécrites avant la recherche
- **MCP Server** : intégration Claude Desktop (les développeurs peuvent interroger le lore depuis leur IDE)

---

**Slide 10 — Sécurité (1 min 30)**

*"Sur un système IA exposé, la sécurité est non-négociable."*

3 couches de protection :

1. **Validation regex** : 57+ patterns contre le prompt injection, jailbreak, injection système
2. **Lakera Guard** (optionnel) : classifier IA externe pour les injections subtiles — mode shadow (log sans bloquer) ou enforce
3. **Masquage PII** : détection et remplacement avant le LLM — emails, téléphones, IPs, cartes bancaires → `[EMAIL]`, `[TEL]`...

Bonus :
- Détection de **spikes** : si +10 tentatives d'injection en 5 minutes → alerte automatique
- Questions **hors-sujet refusées** avec suggestions de questions lore valides

---

**Slide 11 — Monitoring & Observabilité (2 min)**

*"On peut savoir exactement ce qui se passe dans le système en production."*

**Dashboard React temps réel :**
- Statistiques du pipeline (cache hits, requêtes simples vs complexes, reranker activé)
- Historique des reformulations
- Buffer de 1000 logs en mémoire, accessible via `/api/monitoring/logs`

**Langfuse (LLM Tracing) :**
- Chaque appel LLM est tracé avec son contexte, ses sources, son score
- Évaluation automatique LLM-as-Judge

**Supabase (Event Tracking) :**
- Toutes les tentatives d'injection sont enregistrées
- Tous les masquages PII sont loggés
- Feedback utilisateurs (notes 1-5, thumbs)

**Sentry :**
- Erreurs runtime capturées en production

*"C'est ce qui différencie un projet de démo d'un vrai système : on peut le debugger, l'auditer, le monitorer."*

---

## PARTIE 4 — Travail d'équipe, Outils & Bilan (P4) | 5 min

### Slides

**Slide 12 — Workflow Git & GitHub (1 min 30)**

*"On a travaillé comme en entreprise."*

- **Branches feature** : `feature/ingestion`, `main` séparés
- **Commits conventionnels** : `feat:`, `fix:`, `refactor:`, `chore:` — lisibles, filtrables
- **Historique propre** : chaque commit a un message explicite

Montrer (live ou screenshot) :
```
b5c22fe fix: reduce healthcheck start-period to 60s
1044bc0 feat: suggest lore questions when off-topic
0888243 fix: restrict Oracle to lore-only, reject off-topic
a3e1cda fix: block monitoring access without valid key
13f32ef fix: increase default workers to 4
```

- Fichiers sensibles exclus via `.gitignore` (`.env`, clés API)
- `.env.example` pour documenter les variables sans exposer les secrets

---

**Slide 13 — Docker (1 min)**

*"Zéro friction pour déployer ou onboarder un nouveau dev."*

```bash
docker compose up --build -d
# → API disponible sur :8000
# → MCP SSE disponible sur :8001
```

- **Dockerfile multi-stage** : build Node.js (frontend) → runtime Python (API)
- **docker-compose** : orchestre l'app + Redis en un seul fichier
- **Health checks** : vérifie LLM key, Qdrant, BM25, Redis au démarrage
- **Graceful shutdown** : 30 secondes pour finir les requêtes en cours
- **Rotation automatique** des workers (2000 req max pour éviter les fuites mémoire)

---

**Slide 14 — Tests (45 sec)**

- **131 tests unitaires** (pytest + pytest-asyncio)
- Couverture : routes, search, ingestion, auth, PII, cache, watchdog, feedback
- **Tests de charge** (Locust) : 20 utilisateurs simultanés, 4 secondes entre requêtes
- **Makefile** : `make test`, `make setup`, `make docker-up` — workflow reproductible

---

**Slide 15 — Comment on a travaillé en équipe (1 min)**

*"Pas juste diviser le travail — vraiment collaborer."*

- **Découpage par domaine** : chacun propriétaire d'une couche (ingestion, search, sécurité, frontend)
- **Branches dédiées** → revue du code avant merge
- **Convention de nommage partagée** : commits, fichiers, variables
- **Documentation technique** (`docs/DOCUMENTATION.md`) maintenue au fur et à mesure
- **Itérations rapides** : on a refactorisé plusieurs fois (ex: migration du Judge vers Langfuse)

---

**Slide 16 — Récapitulatif des outils maîtrisés (30 sec)**

Tableau rapide — ce que les recruteurs veulent voir :

| Catégorie | Outils |
|-----------|--------|
| **Versioning** | Git, GitHub (branches, commits conventionnels) |
| **Conteneurisation** | Docker, docker-compose |
| **API** | FastAPI, REST, SSE streaming |
| **Frontend** | React, Vite, Tailwind |
| **BDD & Auth** | Supabase (PostgreSQL + JWT) |
| **Cache** | Redis |
| **Tests** | pytest, Locust (load testing) |
| **Monitoring** | Langfuse, Sentry, dashboard custom |
| **Cloud** | Qdrant Cloud, Groq, Cerebras |
| **IA/ML** | RAG, embeddings, LLM, prompt engineering |

---

**Slide 17 — Conclusion & Ce qu'on retient (30 sec)**

- On a construit un système **complet et production-ready**, pas un prototype
- On a appris à **gérer la complexité** : cache, fallbacks, sécurité, monitoring
- On a travaillé avec les **mêmes outils qu'en entreprise**
- Ce projet nous a appris autant sur l'**architecture logicielle** que sur l'IA

*"Merci. Questions ?"*

---

## Notes de préparation

### Ce qu'il faut préparer
- [ ] Schéma du pipeline RAG (Slide 3 + 5) — faire un visuel propre
- [ ] Screenshot du dashboard monitoring (Slide 11)
- [ ] Screenshot des traces Langfuse (Slide 11)
- [ ] Screenshot de l'historique git / commit log (Slide 12)
- [ ] Demo live si possible : poser une question → voir la réponse streamer

### Questions jury anticipées
- **"Pourquoi pas LangChain pour tout ?"** → On l'utilise pour l'intégration Qdrant/LLM, mais on a nos propres couches pour la recherche hybride et le cache pour plus de contrôle
- **"Comment vous gérez la latence ?"** → Cache sémantique Redis + Cerebras (~500ms) + streaming SSE pour la perception
- **"C'est quoi la différence avec ChatGPT ?"** → RAG sur nos données, contrôle total, pas d'hallucination sur le lore, réponses sourcées
- **"Comment vous avez évité les conflits Git ?"** → Branches par feature/personne, chaque dev responsable de son domaine

### Timing de secours
Si on est en avance → montrer la demo live
Si on est en retard → raccourcir la partie Architecture (Slide 7-8 en 30 sec chacun)
