# Documentation Technique — Oracle LoreKeeper

> Document complet expliquant chaque feature du projet, de A a Z.

---

## Table des matieres

1. [Vue d'ensemble](#1-vue-densemble)
2. [Pipeline RAG](#2-pipeline-rag)
3. [Recherche hybride](#3-recherche-hybride)
4. [Generation LLM et fallback](#4-generation-llm-et-fallback)
5. [Ingestion des documents](#5-ingestion-des-documents)
6. [Authentification](#6-authentification)
7. [Memoire conversationnelle](#7-memoire-conversationnelle)
8. [Cache et performance](#8-cache-et-performance)
9. [Securite](#9-securite)
10. [Monitoring et observabilite](#10-monitoring-et-observabilite)
11. [Text-to-Speech et Speech-to-Text](#11-text-to-speech-et-speech-to-text)
12. [Agent ReAct](#12-agent-react)
13. [Serveur MCP](#13-serveur-mcp)
14. [Frontend React](#14-frontend-react)
15. [Deploiement et infrastructure](#15-deploiement-et-infrastructure)
16. [Schema de la base de donnees](#16-schema-de-la-base-de-donnees)
17. [Variables d'environnement](#17-variables-denvironnement)
18. [Tests](#18-tests)
19. [Equipe](#19-equipe)

---

## 1. Vue d'ensemble

Oracle LoreKeeper est un assistant conversationnel base sur le pattern **RAG** (Retrieval-Augmented Generation).
Il repond aux questions des joueurs sur le lore du jeu **Aethelgard Online** en se basant **exclusivement** sur les documents officiels deposes dans le dossier `data/sample/`.

**Principe simple :** l'utilisateur pose une question, le systeme cherche les passages pertinents dans les documents indexes, puis un LLM genere une reponse en citant uniquement ces passages. Rien n'est invente.

### Architecture globale

```
Utilisateur (navigateur)
     |
     v
[ React Frontend ]  <----->  [ FastAPI Backend ]
                                    |
                   +----------------+----------------+
                   |                |                |
             [ Qdrant ]      [ Supabase ]      [ Redis ]
           (vecteurs)      (auth + sessions)   (cache)
                   |                |
            [ FastEmbed ]    [ OpenRouter / Groq / Google ]
           (embeddings)         (LLM)
```

### Qui heberge quoi ?

| Service | Heberge par | Cout |
|---------|-------------|------|
| **FastAPI + React** | Coolify (DigitalOcean) | Cout VPS |
| **Qdrant** | Qdrant Cloud ou meme VPS | Gratuit (1 Go) |
| **Supabase** | Supabase Cloud | Gratuit (500 Mo) |
| **Redis** | Coolify (meme VPS) | Inclus |
| **Google AI / OpenRouter** | Cloud | Pay-per-token |
| **Groq** | Cloud Groq | Gratuit (rate limited) |
| **Langfuse** | Cloud Langfuse | Gratuit (50k obs/mois) |
| **Lakera Guard** | Cloud Lakera | Gratuit (10k req/mois) |
| **FastEmbed** | Local (dans le container) | 0 (CPU, ONNX) |

---

## 2. Pipeline RAG

Le coeur du systeme. Quand un utilisateur pose une question, voici ce qui se passe etape par etape :

```
Question : "Qui est Lucas le Tranchant ?"
     |
     v
1. Masquage PII            -- remplace emails, telephones par [EMAIL], [TEL]
     |
     v
2. Validation securite     -- regex + Lakera Guard (bloque les injections)
     |
     v
3. Cache semantique        -- si une question similaire a deja ete posee, retourne le cache
     |
     v
4. Reformulation           -- LLM rapide (Groq ~500ms) reecrit la question avec le contexte
                              "il fait quelle taille ?" → "Quelle est la taille de Lucas le Tranchant ?"
     |
     v
5. Recherche hybride       -- vecteurs (Qdrant) + BM25 (lexical) → fusion RRF
     |
     v
6. Reranking               -- cross-encoder reordonne les resultats par pertinence
     |
     v
7. Generation LLM          -- le LLM genere la reponse en se basant sur les passages trouves
     |
     v
8. Streaming SSE           -- la reponse arrive token par token dans le navigateur
     |
     v
9. Sauvegarde              -- echange sauvegarde dans Supabase + cache mis a jour (en arriere-plan)
```

**Fichier :** `src/api/routes.py` — endpoint `POST /api/ask`

### Exemple concret

**Requete :**
```json
POST /api/ask
{
  "question": "Qui est Lucas le Tranchant ?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Reponse (SSE stream) :**
```
data: {"type": "meta", "sources": ["personnages.md", "lore.md"], "confidence": 87}
data: {"type": "text", "text": "Lucas le Tranchant est un guerrier"}
data: {"type": "text", "text": " legendaire d'Aethelgard..."}
data: {"type": "done", "model": "gemini-2.0-flash-001"}
```

---

## 3. Recherche hybride

La recherche combine **deux approches** pour trouver les passages pertinents :

### Recherche vectorielle (semantique)

- Les documents sont decoupes en chunks de ~1200 caracteres
- Chaque chunk est transforme en vecteur par **FastEmbed** (modele configurable via `EMBEDDING_MODEL`, defaut `BAAI/bge-m3`, actuellement `intfloat/multilingual-e5-large` — 1024 dimensions)
- Les vecteurs sont stockes dans **Qdrant**
- A la recherche, la question est aussi vectorisee, et Qdrant trouve les vecteurs les plus proches (cosine similarity)

**Exemple :** "Qui est le roi ?" trouve "Le roi Alaric gouverne depuis 200 ans..." meme si le mot "roi" n'apparait pas tel quel.

### Recherche lexicale (BM25)

- Algorithme classique de recherche par mots-cles
- Pondere la frequence des termes et la rarete dans le corpus
- Utile quand la recherche vectorielle rate des termes exacts (noms propres, chiffres)

### Fusion RRF (Reciprocal Rank Fusion)

Les deux listes de resultats sont combinees avec la formule :
```
score(doc) = 1/(60 + rang_vecteur) + 1/(60 + rang_bm25)
```

### Reranking (cross-encoder)

Apres la fusion, un modele **cross-encoder** (`BAAI/bge-reranker-base`) reordonne les resultats.
Contrairement aux embeddings qui comparent question et passage separement, le cross-encoder les lit **ensemble** pour un score de pertinence plus precis.

- Tourne en local via ONNX (pas d'API externe)
- Ajoute ~50-100ms au temps de recherche
- Desactivable via `RERANKER_ENABLED=false`

### Router adaptatif

Le systeme detecte si la question est "simple" ou "complexe" :

| Type | Detection | Comportement |
|------|-----------|-------------|
| Simple | < 6 mots, pas de mot-cle complexe | 5 candidats, pas d'expansion |
| Complexe | >= 6 mots OU mots "comment", "pourquoi", "difference"... | 100 candidats, reranking, expansion possible |

### HyDE (fallback)

Si les scores de recherche sont trop bas (< 0.005), le systeme genere un **document hypothetique** via LLM, l'embedde, et recherche a nouveau. Cela ameliore la couverture sur les questions mal formulees.

**Fichier :** `src/search/search.py`

---

## 4. Generation LLM et fallback

### Chaine de fallback

Le systeme a **4 niveaux** de fallback pour garantir qu'une reponse est toujours generee :

```
Tier 1 : LLM principal  (LLM_MODEL, configurable)
   |  echec (429, timeout, erreur)
   v
Tier 2 : LLM fallback   (FALLBACK_MODEL, configurable)
   |  echec
   v
Tier 3 : Groq dedie     (si GROQ_API_KEY defini)
   |  echec
   v
Tier 4 : Mistral 7B gratuit sur OpenRouter (aucune cle requise)
```

### LLM dedie pour la reformulation

La reformulation utilise un **modele rapide separe** (Groq `llama-3.1-8b-instant` par defaut) au lieu du modele principal. Cela reduit le temps avant le premier token de 2-5s a ~500ms.

- Configurable via `REFORMULATION_MODEL` et `GROQ_API_KEY`
- Fallback automatique sur `_llm_fallback` puis `_llm` si Groq indisponible
- Desactivable via `REFORMULATION_ENABLED=false`

### Streaming

La reponse est streamee token par token via **Server-Sent Events (SSE)**.
Le LLM genere les tokens dans un thread separe, et une queue `asyncio.Queue` les transmet a la boucle FastAPI sans bloquer.

### Reformulation de question

Quand l'utilisateur dit "il fait quelle taille ?", le systeme regarde l'historique et reformule :
→ "Quelle est la taille de Lucas le Tranchant ?"

Cela ameliore la recherche car la question reformulee est autonome et precise.

- Ignore les questions < 5 mots sans historique (economise un appel LLM)
- Historique de reformulation stocke dans une `deque(maxlen=50)` en memoire

### Langfuse (observabilite LLM)

Chaque appel LLM est trace dans **Langfuse** :
- Modele utilise, tokens consommes, latence
- Question posee, reponse generee
- Permet de debugger les reponses de mauvaise qualite

**Fichier :** `src/generation/generator.py`

---

## 5. Ingestion des documents

### Formats supportes

Deux modes de parsing selectionnable via `PARSER_MODE` dans le `.env` :

**Mode `custom` (defaut) — parser maison par format :**

| Format | Parser |
|--------|--------|
| `.txt`, `.md` | Lecture directe UTF-8 |
| `.csv` | Detection dialect + rendu ligne par ligne |
| `.json` | Aplatissement recursif JSON → texte cle: valeur |
| `.xlsx` | openpyxl — rendu "Colonne: Valeur" par ligne |
| `.xml` | xml.etree — extraction texte (ignore balises) |
| `.pdf` | LlamaParse si `LLAMA_CLOUD_API_KEY` defini, sinon Unstructured |

**Mode `unstructured` — Unstructured gere tout :**

| Format | Parser |
|--------|--------|
| `.txt`, `.md`, `.csv`, `.xlsx`, `.xml`, `.pdf` | Unstructured (26+ formats, tables, images) |
| `.json` | Parser custom (toujours — Unstructured produit un moins bon texte pour JSON) |
| Tous les formats | Fallback automatique vers parser custom si Unstructured echoue |

### Processus d'indexation

```
1. Scan data/sample/           -- detecte nouveaux/modifies/supprimes
2. Parsing                     -- extrait le texte de chaque fichier
3. Validation lore             -- LLM verifie que le contenu est du lore (singleton _llm_checker, max_tokens=10)
4. Enrichissement contextuel   -- LLM genere un resume + liste d'entites (singleton _llm_summarizer, max_tokens=400)
                                  Cache Redis 24h sur hash MD5 du texte
5. Chunking                    -- decoupe en morceaux de 1200 chars (overlap 200)
6. Embedding                   -- FastEmbed transforme chaque chunk en vecteur
7. Indexation Qdrant           -- upsert dans la collection "lore"
8. Index BM25                  -- reconstruit le corpus pour la recherche lexicale
9. Sauvegarde memoire          -- files_metadata.json (hash + mtime par fichier)
```

### Indexation incrementale

Le systeme ne reindexe que les fichiers modifies. Il compare les dates de modification.
Pour forcer une reindexation complete : `POST /api/reindex {"force": true}`

### Watchdog

Un observateur surveille le dossier `data/sample/`. Si un fichier est ajoute, modifie ou supprime, la reindexation se declenche automatiquement apres un delai (configurable via `DEBOUNCE_MS`, defaut 10s).

**Fichiers :** `src/ingestion/run.py`, `src/ingestion/chunker.py`, `src/ingestion/parser.py`, `src/ingestion/watcher.py`

---

## 6. Authentification

### Supabase Auth (production)

Le frontend utilise le SDK Supabase pour l'authentification :

| Methode | Comment |
|---------|---------|
| Email + mot de passe | Formulaire classique signup/login |
| GitHub OAuth | Bouton "Continuer avec GitHub" |
| Google OAuth | Bouton "Continuer avec Google" |

Le SDK stocke un **JWT** dans le navigateur. Chaque requete API inclut ce token dans le header `Authorization: Bearer <token>`.

Le backend verifie le JWT via l'API Supabase Auth avec un **cache de 60 secondes** (evite de revalider le meme token a chaque requete).

### Mode invite (developpement)

En local sans Supabase, le frontend genere un ID guest aleatoire (`guest_abc123`) stocke dans `localStorage`. Le backend l'accepte via le header `x-local-guest-id`.

### Cle monitoring

Le dashboard `/monitoring` est protege par une cle secrete (`MONITORING_KEY`). Elle est envoyee dans le header `X-Monitoring-Key`.

**Fichiers :** `src/api/auth.py`, `src/frontend-react/src/auth.js`

---

## 7. Memoire conversationnelle

Le systeme a **3 niveaux** de memoire :

### Memoire court-terme (historique de session)

- Les 5 derniers echanges (question + reponse) de la conversation en cours
- Injectes directement dans le prompt LLM
- Stockes dans Supabase (`conversations` + `messages`)

**Exemple :** si l'utilisateur demande "Qui est Lucas ?" puis "Ou vit-il ?", le LLM voit les deux echanges et comprend que "il" = Lucas.

### Memoire long-terme (resume utilisateur)

- Toutes les `SUMMARY_UPDATE_INTERVAL` interactions (defaut 5), un **resume** est genere par le LLM
- La verification du compteur tourne en **arriere-plan** (thread pool) pour ne pas bloquer le stream
- Stocke dans Supabase (`user_memory`) — un seul resume par utilisateur
- Contient : faits importants, personnages explores, preferences, objectifs
- Limite a 150 mots

**Exemple :** "L'utilisateur s'interesse principalement a la faction des Forgerons et au personnage Lucas. Il explore la region nord d'Aethelgard."

### Memoire vectorielle (optionnelle)

- Chaque echange important est embedde et stocke dans Qdrant (`user_memories`)
- A la prochaine question, les 3-5 echanges les plus similaires sont recuperes
- Permet de retrouver des informations vieilles de plusieurs sessions
- Activable via `VECTOR_MEMORY_ENABLED=true`

**Fichiers :** `src/monitoring/tracker.py`, `src/memory/vector_memory.py`

---

## 8. Cache et performance

Le systeme a **3 couches de cache** :

### Cache de recherche (Redis)

- **Quoi :** resultats de recherche (passages + sources + scores)
- **Cle :** hash MD5 de la question normalisee
- **TTL :** 300 secondes (5 minutes)
- **Ou :** Redis si disponible, sinon dictionnaire en memoire
- **Invalidation :** automatique apres reindexation

**Exemple :** si 10 utilisateurs posent "Qui est le roi ?", seul le premier declenchera une recherche. Les 9 suivants recevront le resultat du cache en < 50ms.

### Cache semantique (Redis + matrice numpy)

- **Quoi :** reponses LLM completes
- **Cle :** embedding de la question (cosine similarity > seuil configurable)
- **TTL :** 1 heure
- **Ou :** Redis uniquement (desactive sans Redis)
- **Taille max :** 5000 entrees (compteur Redis INCR, pas de scan complet)

**Implementation O(1) :** les embeddings sont charges depuis Redis en **2 round-trips** (SCAN + MGET) et stockes dans une **matrice numpy normalisee en memoire**. La similarite cosine est calculee par un produit matriciel vectorise (`matrix @ q_arr`). La matrice est reconstruite toutes les 120 secondes (configurable via `MATRIX_REFRESH_INTERVAL`).

**Difference avec le cache de recherche :** le cache de recherche est un match exact (meme question = meme resultats). Le cache semantique est un match flou ("Qui est le roi ?" et "Parle-moi du roi" retournent le meme cache).

### Cache JWT (memoire)

- **Quoi :** resultats de verification JWT Supabase
- **TTL :** 60 secondes
- **Ou :** memoire du processus (LRU, 512 entrees max)

### Impact sur la RAM

| Composant | Memoire estimee |
|-----------|----------------|
| FastEmbed (modele ONNX) | ~300-500 Mo |
| BM25 corpus (10k chunks) | ~50-100 Mo |
| Cross-encoder reranker | ~100-200 Mo |
| Matrice numpy semantic cache | ~negligeable |
| Application Python | ~100 Mo |
| **Total par worker** | **~600 Mo - 1 Go** |

Avec 2 workers Gunicorn, prevoir **~1.5-2 Go de RAM** minimum.

**Fichiers :** `src/search/search.py`, `src/caching/semantic_cache.py`

---

## 9. Securite

### 2 couches de protection

```
Requete utilisateur
     |
     v
Couche 1 : Regex              -- patterns d'injection connus (instantane)
     |                            "ignore instructions", "tu es maintenant",
     |                            "system prompt", "[SYSTEM]", etc.
     v
Couche 2 : Lakera Guard       -- detecteur ML anti-attaque (API externe)
     |                            ecoute uniquement le detecteur "prompt_attack"
     |                            ignore pii/name, moderated_content (geres ailleurs)
     v
Resultat : {valid: true/false, type: "ok" | "prompt_injection"}
```

### Lakera Guard

Service ML specialise dans la detection d'attaques de prompt.

- Appel API < 50ms
- Cache Redis de 60 secondes (evite les appels redondants)
- Modes : `enforce` (bloque), `shadow` (log seulement), `disabled`
- **Detecteur ecoute :** uniquement `prompt_attack` (les detecteurs `pii/*` et `moderated_content/*` sont ignores — le PII est gere par `pii_masker.py` et les questions lore contiennent des prenoms legaux)
- Fail-open si l'API Lakera est indisponible

### Masquage PII

Avant la validation, les informations personnelles sont masquees :

| Type | Avant | Apres |
|------|-------|-------|
| Email | `john@gmail.com` | `[EMAIL]` |
| Telephone | `+32 470 123 456` | `[TEL]` |
| Carte bancaire | `4532 1234 5678 9012` | `[CARTE]` |
| Adresse IP | `192.168.1.1` | `[IP]` |

### LLM-as-a-Judge

Quand un utilisateur met un pouce en bas (rating <= 2), le systeme :
1. Recupere la derniere question + reponse
2. Envoie au LLM pour evaluation (score 0.0 - 1.0)
3. Si score < 0.5, log un evenement `judge_flag` dans Supabase
4. Le score est stocke dans la table `feedback`

### Langfuse online evaluators (LLM-as-a-judge)

Evaluation automatique de chaque generation via les evaluateurs Langfuse configures dans l'UI :

| Score | Ce qu'il mesure |
|-------|----------------|
| `Correctness` | La reponse est-elle correcte par rapport au lore ? |
| `Contextrelevance` | Les passages recuperes sont-ils pertinents a la question ? |
| `Hallucination` | La reponse contient-elle des informations inventees ? |

Les scores (0-1) sont calcules automatiquement apres chaque generation et stockes dans Langfuse. Visualisation disponible dans le dashboard Langfuse → Scores.

**Configuration :** UI Langfuse → Evaluations → LLM-as-a-judge

**Fichiers :** `src/security/validator.py`, `src/security/pii_masker.py`, `src/security/judge.py`

---

## 10. Monitoring et observabilite

### Dashboard `/monitoring`

Interface d'administration accessible avec la cle `MONITORING_KEY`.

**Metriques affichees :**
- Total questions, erreurs, tentatives d'injection
- Latence P50 (mediane)
- Nombre de vecteurs dans Qdrant
- Distribution requetes simples vs complexes

**Actions disponibles :**
- Forcer une reindexation
- Uploader un fichier lore (drag & drop)
- Activer/desactiver la reformulation
- Voir les logs systeme en temps reel

### Evenements traces (Supabase)

Chaque action significative est enregistree :

| Evenement | Quand |
|-----------|-------|
| `question` | Question posee (avec latence) |
| `error` | Erreur LLM ou recherche |
| `injection_regex` | Pattern d'injection detecte |
| `injection_lakera` | Lakera Guard a bloque |
| `rate_limit` | Rate limit depasse |
| `fallback` | Bascule vers LLM de secours |
| `upload` | Fichier uploade par admin |
| `reindex` | Reindexation declenchee |
| `tts` / `voice` | Audio genere / transcrit |

### Detection de spike

Si plus de **10 tentatives d'injection en 5 minutes**, le systeme :
1. Log un warning
2. Envoie une alerte Sentry (si configure)

### Langfuse

Traces detaillees de chaque appel LLM :
- Modele utilise, tokens, latence
- Question originale et reformulee
- Modele de reformulation separe visible dans les traces

**Fichiers :** `src/monitoring/tracker.py`, `src/api/blueprints/monitoring_bp.py`

---

## 11. Text-to-Speech et Speech-to-Text

### TTS (texte → audio)

- **Service :** Edge TTS (Microsoft) — gratuit, pas de cle API
- **Voix :** `fr-FR-HenriNeural` (francais, masculin)
- **Format :** MP3
- **Limite :** 2000 caracteres max par requete, 30 requetes/minute

**Utilisation :** bouton haut-parleur a cote de chaque reponse dans le chat.

### STT (audio → texte)

- **Service :** Whisper Large v3 (via Groq)
- **Formats :** webm, wav, mp3, ogg, mp4, m4a
- **Limite :** 10 Mo max, 20 requetes/minute
- **Detection :** langue automatique (FR + EN)

**Utilisation :** bouton micro dans la barre de saisie du chat.

**Fichier :** `src/api/blueprints/media.py`, `src/tts/tts.py`

---

## 12. Agent ReAct

Alternative au pipeline RAG classique. L'agent ReAct (Reasoning + Acting) suit une boucle :

```
Pensee : "L'utilisateur demande qui est Lucas. Je dois chercher dans les documents."
     |
     v
Action : search_rag("Lucas le Tranchant")
     |
     v
Observation : "Lucas est un guerrier de la faction des Forgerons..."
     |
     v
Pensee : "J'ai trouve la reponse. Je peux repondre."
     |
     v
Reponse finale : "Lucas le Tranchant est un guerrier legendaire..."
```

- Maximum 3 iterations (pour eviter les boucles infinies)
- Endpoint : `POST /api/ask_agent`
- Securite identique a `/api/ask` : PII masquage + validation injection

**Fichier :** `src/agent/react_agent.py`

---

## 13. Serveur MCP

Le **Model Context Protocol** (MCP) permet a des clients comme **Claude Desktop**, **Cursor** ou **Claude.ai** de se connecter au RAG.

### Outils exposes

| Outil | Description | Retour |
|-------|-------------|--------|
| `ask_lore(question)` | Poser une question au RAG | Reponse texte + sources |
| `search_lore(query)` | Rechercher des passages sans generation | Passages + sources |

### Ressources exposees

| Ressource | Description |
|-----------|-------------|
| `lore://sources` | Liste des fichiers indexes |
| `lore://stats` | Statistiques de la collection Qdrant |

### Modes de transport

| Mode | Usage | Comment |
|------|-------|---------|
| **Stdio** | Claude Desktop (local) | `python mcp_server.py` |
| **SSE** | Claude.ai, Cursor (distant) | Port 8001, lance par `start.sh` |

### Configuration Claude Desktop

```json
{
  "mcpServers": {
    "lorekeeper": {
      "command": "python",
      "args": ["C:/chemin/vers/mcp_server.py"],
      "env": {
        "OPENAI_API_KEY": "gsk_...",
        "QDRANT_URL": "https://...",
        "QDRANT_API_KEY": "..."
      }
    }
  }
}
```

**Fichier :** `mcp_server.py`

---

## 14. Frontend React

### Stack technique

| Technologie | Version | Role |
|------------|---------|------|
| React | 19 | Framework UI |
| React Router | 7 | Navigation SPA |
| Tailwind CSS | 4 | Styles |
| Framer Motion | 12 | Animations |
| Lucide React | 1.7 | Icones |
| Supabase JS | 2.101 | Authentification |
| Vite | 8 | Build tool |

### Pages

**Page Login/Signup (`App.jsx`)**
- Formulaires email/mot de passe
- Boutons OAuth (GitHub, Google)
- Gestion des erreurs de formulaire

**Page Chat (`ChatPage.jsx`)**
- Sidebar : liste des conversations, bouton nouveau chat
- Zone de chat : messages user/assistant, streaming en temps reel
- Sources et score de confiance affiches sous chaque reponse
- Boutons pouce haut/bas pour le feedback
- TTS (lecture audio) et STT (dictee vocale)
- Rendu Markdown (gras, italique, blocs de code avec bouton copier)

**Page Monitoring (`MonitoringPage.jsx`)**
- Dashboard de statistiques (questions, erreurs, injections)
- Pipeline inspector (vecteurs, BM25, reranker)
- Upload drag & drop de fichiers lore
- Logs systeme en temps reel
- Toggle reformulation

### Build

```bash
cd src/frontend-react
npm install
npm run build    # → genere dans src/frontend/assets/
```

Le build React est servi par FastAPI comme fichiers statiques.

**Dossier :** `src/frontend-react/`

---

## 15. Deploiement et infrastructure

### Docker

```dockerfile
FROM python:3.11-slim
# Installe libmagic, poppler, tesseract, curl
# Copie requirements.txt et installe les deps Python
# Expose ports 8000 (API) et 8001 (MCP SSE)
# Healthcheck sur /health (interval 30s, timeout 10s, start 120s)
# CMD : ./start.sh
```

### start.sh

```bash
#!/bin/sh
# 1. Lance le serveur MCP SSE sur le port 8001 en arriere-plan
MCP_TRANSPORT=sse MCP_PORT=8001 python mcp_server.py &

# 2. Lance FastAPI via Gunicorn sur le port 8000
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 2 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --max-requests 500 \
  --max-requests-jitter 50
```

### Coolify

1. Creer un service **Docker** dans Coolify
2. Connecter le depot Git (branche `main`)
3. Ajouter les variables d'environnement (voir section 17)
4. Ajouter un service **Redis** dans Coolify, copier l'URL interne comme `REDIS_URL`
5. Ajouter un service **Qdrant** dans Coolify, ou utiliser Qdrant Cloud
6. Le healthcheck est integre dans le Dockerfile
7. Push sur `main` → deploiement automatique

### Charge et mise a l'echelle

| Parametre | Valeur | Explication |
|-----------|--------|-------------|
| Workers Gunicorn | 2 | 2 processus Python independants |
| RAM par worker | ~600 Mo - 1 Go | Modeles ONNX en memoire |
| RAM totale recommandee | 2 Go | 2 workers + Redis + overhead |
| CPU recommande | 2 vCPU | Suffisant pour reranking ONNX |
| Requetes max/worker | 500 | Puis restart auto (evite fuites memoire) |
| Rate limit | 10 questions/min/user | Protection contre le spam |
| Timeout | 120s | Pour les reponses longues via LLM |

---

## 16. Schema de la base de donnees

Heberge sur **Supabase** (PostgreSQL).

```
+------------------+     +------------------+
|  conversations   |     |    messages       |
+------------------+     +------------------+
| id (PK)          |<--->| conversation_id   |
| session_id (UUID)|     | role (user/asst)  |
| user_id (UUID)   |     | content (TEXT)    |
| created_at       |     | user_id           |
+------------------+     | created_at        |
                         +------------------+

+------------------+     +------------------+
|  user_memory     |     |    events         |
+------------------+     +------------------+
| user_id (PK)     |     | id (PK)           |
| summary (TEXT)   |     | type (VARCHAR)    |
| updated_at       |     | detail (TEXT)     |
+------------------+     | latency_ms (INT)  |
                         | created_at        |
+------------------+     +------------------+
|    feedback      |
+------------------+
| id (PK)          |
| session_id       |
| user_id          |
| rating (1-5)     |
| comment          |
| judge_score      |
| created_at       |
+------------------+
```

Le backend utilise la cle `service_role` pour acceder a toutes les tables sans restriction RLS.
Le frontend utilise la cle `anon` pour l'authentification uniquement.

---

## 17. Variables d'environnement

### Essentielles (obligatoires)

| Variable | Description | Exemple |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | Cle API LLM principal | `sk-or-...` |
| `LLM_BASE_URL` | URL de l'API LLM | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `LLM_MODEL` | Modele principal | `gemini-2.0-flash-001` |
| `QDRANT_URL` | URL Qdrant | `https://xxx.qdrant.io:6333` |
| `QDRANT_API_KEY` | Cle Qdrant Cloud | `xxx` |
| `SUPABASE_URL` | URL Supabase | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Cle service Supabase | `eyJ...` |
| `SUPABASE_ANON_KEY` | Cle publique Supabase | `eyJ...` |
| `MONITORING_KEY` | Mot de passe monitoring | `votre_secret` |

### Production

| Variable | Description | Defaut |
|----------|-------------|--------|
| `REDIS_URL` | Redis partage | memoire locale |
| `GROQ_API_KEY` | Cle Groq (reformulation + fallback) | — |
| `GROQ_MODEL` | Modele Groq fallback | `llama-3.1-8b-instant` |
| `FALLBACK_API_KEY` | Cle LLM fallback Tier 2 | — |
| `FALLBACK_BASE_URL` | URL LLM fallback Tier 2 | Groq |
| `FALLBACK_MODEL` | Modele fallback Tier 2 | `llama-3.1-8b-instant` |
| `ALLOWED_ORIGINS` | CORS (domaine Coolify) | `*` |
| `LAKERA_API_KEY` | Lakera Guard | — |
| `LAKERA_MODE` | `enforce` / `shadow` / `disabled` | `enforce` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse | — |
| `LANGFUSE_SECRET_KEY` | Langfuse | — |
| `SENTRY_DSN` | Sentry errors | — |

### Feature flags

| Variable | Defaut | Description |
|----------|--------|-------------|
| `RERANKER_ENABLED` | `true` | Cross-encoder actif |
| `VECTOR_MEMORY_ENABLED` | `false` | Memoire vectorielle par utilisateur |
| `QUERY_EXPANSION_ENABLED` | `false` | Variantes de requete via LLM |
| `REFORMULATION_ENABLED` | `true` | Reformulation contextuelle |
| `SECURITY_VALIDATOR` | `rules` | `true` (regex+Lakera) / `rules` (regex only) / `false` |
| `PARSER_MODE` | `custom` | `custom` ou `unstructured` (26+ formats) |

### Tuning

| Variable | Defaut | Description |
|----------|--------|-------------|
| `CONVERSATION_DEPTH` | `5` | Echanges injectes dans le contexte |
| `SUMMARY_UPDATE_INTERVAL` | `5` | Frequence MAJ du resume utilisateur |
| `SEARCH_CACHE_TTL` | `300` | Duree cache recherche (sec) |
| `SEARCH_CACHE_SIZE` | `100` | Taille max cache memoire |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modele embeddings FastEmbed |
| `RERANKER_MODEL` | `BAAI/bge-reranker-base` | Modele reranker ONNX |
| `REFORMULATION_MODEL` | `llama-3.1-8b-instant` | Modele rapide pour reformulation (Groq) |
| `MATRIX_REFRESH_INTERVAL` | `120` | Frequence rebuild matrice cache semantique (sec) |
| `LAKERA_CACHE_TTL` | `60` | TTL cache Redis Lakera (sec) |
| `DEBOUNCE_MS` | `10000` | Delai reindexation watchdog (ms) |

---

## 18. Tests

```bash
# Tous les tests unitaires
python -m pytest src/test-unitaires/ --ignore=src/test-unitaires/test_load.py -v

# Tests de charge (necessite serveur actif sur localhost:8080)
python -m pytest src/test-unitaires/test_load.py -v
```

### Couverture

| Fichier test | Ce qu'il teste |
|-------------|----------------|
| `test_routes.py` | Endpoints API (ask, reindex, reformulation) |
| `test_search.py` | Pipeline hybride, router, BM25, reranker |
| `test_generator.py` | Generation LLM, fallback, reformulation, deque |
| `test_vector_store.py` | Operations Qdrant (ajout, suppression, recherche) |
| `test_run.py` | Ingestion, detection de changements, indexation |
| `test_chunker.py` | Decoupage en chunks |
| `test_document_loader.py` | Parsing multi-format |
| `test_tracker.py` | Supabase events + conversations (UUID valides) |
| `test_integration.py` | Flux complet bout-en-bout (SSE parse) |
| `test_auth_flow.py` | Scenarios d'authentification |
| `test_feedback.py` | Feedback human-in-the-loop |
| `test_confidence_score.py` | Calcul du score de confiance |
| `test_validator_lakera.py` | Securite : regex, Lakera prompt_attack, PII ignore, shadow |
| `test_pii_masker.py` | Masquage d'informations personnelles |
| `test_watchdog.py` | Surveillance fichiers (debounce patche a 0.3s) |
| `test_load.py` | Tests de charge 1000 users (necessite serveur actif) |

**Resultat actuel :** 124/124 tests unitaires passes — 5 tests de charge necessitent un serveur actif.

---

## 19. Equipe

Projet realise par :

- **Emir**
- **Nicolas**
- **Ediz**
- **Tom**

---

*Derniere mise a jour : Avril 2026*
