# Schémas des features

Ce document regroupe les schémas principaux du projet **HELMo Oracle / LoreKeeper**.
Il sert de support de présentation et de vue d'ensemble fonctionnelle.

## 1. Carte des features

```mermaid
flowchart TD
    A[HELMo Oracle / LoreKeeper] --> B[Chat RAG]
    A --> C[Sécurité]
    A --> D[Monitoring]
    A --> E[Ingestion]
    A --> F[Authentification]
    A --> G[Audio]
    A --> H[Agent MCP]
    A --> I[Déploiement]

    B --> B1[Recherche hybride
Vectoriel + BM25 + RRF]
    B --> B2[Cache sémantique]
    B --> B3[Reformulation contextuelle]
    B --> B4[Mémoire 3 niveaux]
    B --> B5[Streaming SSE]
    B --> B6[Fallback LLM 4 tiers]

    C --> C1[Regex anti-injection]
    C --> C2[Lakera Guard]
    C --> C3[Masquage PII]
    C --> C4[LLM-as-a-Judge]

    D --> D1[Dashboard /monitoring]
    D --> D2[Logs temps réel]
    D --> D3[Stats pipeline]
    D --> D4[Reindexation]

    E --> E1[Parsing multi-format]
    E --> E2[Chunking]
    E --> E3[Embeddings Qdrant]
    E --> E4[Watchdog auto-reindex]

    F --> F1[Supabase Auth]
    F --> F2[GitHub OAuth]
    F --> F3[Google OAuth]
    F --> F4[Mode guest local]

    G --> G1[TTS Edge]
    G --> G2[STT Whisper]

    H --> H1[ask_lore]
    H --> H2[search_lore]
    H --> H3[Ressources lore://]

    I --> I1[Docker]
    I --> I2[Gunicorn]
    I --> I3[Coolify]
    I --> I4[Redis + Qdrant]
```

## 2. Flux d'une question utilisateur

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant F as Frontend React
    participant A as API FastAPI
    participant S as Sécurité
    participant C as Cache / Recherche
    participant G as Génération LLM
    participant B as Base (Supabase/Qdrant)

    U->>F: Pose une question
    F->>A: POST /api/ask
    A->>S: Vérification entrée
    S-->>A: ok / rejet
    A->>C: Cache sémantique
    C-->>A: hit / miss
    A->>C: Recherche hybride + reranking
    C->>B: Qdrant + BM25 + mémoire
    B-->>C: Passages + sources
    C-->>A: Contexte récupéré
    A->>G: Génération avec mémoire + contexte
    G-->>A: Réponse streamée
    A-->>F: SSE token par token
    F-->>U: Réponse affichée
```

## 3. Chaîne de sécurité

```mermaid
flowchart TD
    Q[Requête utilisateur] --> R[Regex anti-injection]
    R -->|OK| L[Lakera Guard]
    R -->|Bloqué| X[Retour erreur sécurité]
    L -->|OK| P[Masquage PII]
    L -->|Bloqué| Y[Retour prompt_injection / jailbreak]
    P --> Z[Validation finale]
    Z --> O[Envoi au pipeline RAG]
```

## 4. Monitoring et exploitation

```mermaid
flowchart LR
    A[API / Chat / Ingestion] --> T[Tracker events]
    T --> S[Supabase events]
    T --> L[Buffer logs mémoire]
    T --> F[Langfuse traces]
    S --> D[Dashboard /monitoring]
    L --> D
    F --> D
    D --> R[Reindexation manuelle]
    D --> U[Upload de fichiers lore]
    D --> M[Toggle reformulation]
```

## 5. Résumé fonctionnel

| Domaine | Ce que ça apporte |
|---|---|
| Chat RAG | Réponses basées sur les documents officiels |
| Sécurité | Réduction des injections, masquage PII, détection des abus |
| Monitoring | Visibilité sur les erreurs, les logs et les performances |
| Ingestion | Ajout facile de nouveaux fichiers lore |
| Auth | Connexion user + OAuth + mode guest en dev |
| Audio | Lecture audio et dictée vocale |
| Agent MCP | Connexion à Claude Desktop / Cursor / Claude.ai |
