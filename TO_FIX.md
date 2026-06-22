# RABELIA — Fixes avant mise en vente
> Audit du 2026-06-12 — repo `ForgedEmir/RAG`, branche `Emir`
> Verdict : techniquement solide, mais 3 fuites multi-tenant bloquantes + packaging à finir.

---

## 🔴 PRIORITÉ 1 — Isolation multi-tenant (BLOQUANT, deal-breaker B2B)

Un client peut actuellement lire les documents d'un autre client. La plomberie existe mais n'est pas branchée.

- [ ] **`/api/ask` ne filtre pas par tenant** — `src/api/routes.py:316`
  - Actuel : `await search_passages(query)` → cherche dans TOUS les tenants
  - Fix : `tenant_id = await get_tenant_id(user_id)` puis `await search_passages(query, tenant_id=tenant_id)`
  - Le paramètre existe déjà : `src/search/search.py:406`

- [ ] **BM25 est global, aucun filtre tenant** — `src/search/search.py:446-463`
  - Le corpus BM25 est un fichier unique partagé entre tous les tenants
  - Fix : soit un corpus BM25 par tenant, soit stocker `tenant_id` dans chaque entrée du corpus et filtrer les résultats AVANT la fusion RRF
  - ⚠️ Même si le vectoriel est filtré, BM25 fuit quand même → les deux sont nécessaires

- [ ] **Cache sémantique global** — `src/api/routes.py:268` + `src/caching/semantic_cache.py:178`
  - `cache_check(question)` keyé uniquement sur la similarité → la réponse cachée du tenant B peut être servie au tenant A (sources comprises)
  - Fix : namespacer les clés Redis par `tenant_id` (`cache:{tenant_id}:...`) et passer `tenant_id` à `check()` / `store()`

- [ ] **MCP server sans tenant** — `src/mcp_server.py:159` et `:192`
  - `search_passages()` appelé sans tenant_id
  - Mitigé : port 8001 non publié dans docker-compose, mais à corriger ou documenter clairement

- [ ] **Test d'intégration d'isolation** (preuve pour les acheteurs)
  - User A upload un doc → user B pose une question dessus → vérifier 0 passage, 0 cache hit, 0 résultat BM25

## 🔴 PRIORITÉ 2 — Juridique / packaging de vente

- [ ] **Ajouter un fichier LICENSE** (décider : licence commerciale ? SaaS ?)
  - Bonne nouvelle : deps en Apache/MIT (MiniLM, ms-marco, FastEmbed, FastAPI) → pas de blocage
- [ ] **Réécrire le README** : il vend "Oracle LoreKeeper / Aethelgard Online / Minecraft" alors que le produit est RABELIA (recherche documentaire B2B). Un acheteur voit un projet étudiant gaming.
- [ ] **Purger les fichiers embarrassants** :
  - `docs/EXAM_REVIEW.md` (115 KB de notes de révision d'examen)
  - `frontend/design-canvas.jsx`, `screen-*.jsx`, `tweaks-panel.jsx`
  - `RABELIA - Canvas.html`, `RABELIA - Prototype.html`
  - `frontend/dist/` commité (2,6 MB — déjà généré par le Dockerfile)
- [ ] **Corriger les chemins dans le README** : il référence `src/test-unitaires/` mais les tests sont dans `src/tests/`

## 🟠 PRIORITÉ 3 — Robustesse prod

- [ ] **CI/CD** : aucune actuellement. Minimum : GitHub Actions avec `pytest` + build Docker sur chaque PR (27 fichiers de tests existent déjà, autant les exécuter automatiquement)
- [ ] **Pinner `requirements.txt`** : tout est en `>=` → build non reproductible, une release LangChain peut casser la prod. Utiliser `pip-compile` ou pinner à la main
- [ ] **Facturation tokens réels** — `src/api/routes.py:398` : `len(text) // 4` est une estimation. Pour facturer du B2B, récupérer `usage_metadata` renvoyé par LangChain
- [ ] **Cache des assets en prod** — `main.py:494-499` : `no-store` sur `/assets/` → chaque visite retélécharge ~1 MB de JS. Les assets Vite sont hashés → mettre `Cache-Control: max-age=31536000, immutable`
- [ ] **Suppression complète des données (RGPD)** : vérifier que `/api/admin/delete` supprime aussi les points Qdrant + l'entrée du corpus BM25 + les entrées de cache du fichier

## ✅ Déjà bon (arguments de vente)

- Hybrid search : vector + BM25 + RRF + reranker ONNX conditionnel + HyDE + multi-query — sans PyTorch (déploiement CPU léger)
- Fallback LLM auto Cerebras→Groq avec tracking, streaming SSE
- Sécurité : `hmac.compare_digest`, anti zip-slip/zip-bomb, logs sanitisés, masquage PII, Lakera optionnel, headers sécurité, Docker non-root, guest mode off par défaut
- Aucun secret commité, `.env.example` documenté
- Observabilité : Langfuse, Sentry, dashboard monitoring, healthchecks

## 📋 Ordre d'exécution suggéré

1. Isolation tenant (ask + BM25 + cache + MCP) + test d'isolation — **~1-3 jours** (le gros morceau = BM25)
2. Nettoyage repo + README produit + LICENSE — ~½ journée
3. CI GitHub Actions — ~½ journée
4. Pin deps + tokens réels — ~½ journée
5. Load test Locust (déjà dans le repo) sur une instance déployée avec 2 tenants réels