# LoreKeeper — État du projet (branche Emir)

> Document interne · À lire avant la présentation

---

## Ce que fait le projet aujourd'hui

L'Oracle LoreKeeper répond aux questions des joueurs sur le lore d'Aethelgard Online.
Il ne cherche pas sur internet, n'invente rien — il lit uniquement nos documents officiels.

**Flux complet :**
```
Question joueur
    → Sécurité (Lakera Guard + regex) — bloque les injections
    → Réécriture (LLM reformule si question de suivi)
    → Recherche sémantique Qdrant (5 passages les plus proches)
    → Génération LLM Groq en streaming
    → Réponse affichée token par token + bouton écouter (TTS)
    → Sauvegarde de l'échange en base (mémoire multi-sessions)
```

---

## Ce que Marcus demandait vs ce qu'on a

| Technologie demandée | Statut | Ce qu'on utilise |
|---|---|---|
| **LangChain** | ✅ Intégré | Orchestration LLM, prompts, chaînes RAG |
| **Qdrant** | ✅ Intégré | Base vectorielle cloud, k=5 passages |
| **Unstructured.io** | ✅ Intégré | Parse .md .txt .csv .json .xlsx .xml |
| **LlamaIndex** | — | Non intégré (LangChain couvre le besoin) |
| **LlamaParse** | — | Non intégré (voir section ci-dessous) |
| **pgvector** | — | Qdrant Cloud utilisé à la place |
| **Pinecone** | — | Qdrant Cloud utilisé à la place |
| **Weaviate** | — | Qdrant Cloud utilisé à la place |
| **OpenAI Embeddings** | — | FastEmbed `paraphrase-multilingual-MiniLM` (gratuit, local) |
| **Vercel AI SDK** | — | SSE natif Flask (même résultat, pas de dépendance Vercel) |

---

## Ce que Marcus voulait sur le code — tout respecté ✅

- Pas de notebooks en production → **code Python structuré en modules**
- Type Hints → **présents dans toutes les fonctions**
- Tests qui valident → **77 tests pytest, 77/77 passent**
- Pipeline robuste (ne plante pas sur fichier corrompu) → **try/except partout, fail-silent**

---

## LlamaParse — c'est quoi, et pourquoi on l'a pas

**LlamaParse** (par LlamaIndex) est un parseur de documents basé sur un LLM.
Il est particulièrement fort pour extraire le contenu de **PDFs complexes** : tableaux imbriqués, colonnes multiples, formulaires, images avec texte.

Notre parseur actuel (Unstructured) gère déjà tous nos formats actuels correctement.
LlamaParse devient utile si on doit ingérer :
- Des PDFs de design docs ou de bibles narratives très formatées
- Des documents avec des tableaux complexes mal lus par Unstructured

**Pour l'intégrer si le prof l'exige :**
```python
pip install llama-parse
```
```python
from llama_parse import LlamaParse
parser = LlamaParse(api_key="...", result_type="markdown")
documents = parser.load_data("bible_narrative.pdf")
```
Il retourne du Markdown propre qu'on peut ensuite chunker normalement.
Il faut une clé API LlamaCloud (plan gratuit disponible).

---

## Stack active en production

```
Flask 3 + Gunicorn + Gevent     → API + streaming SSE
LangChain                        → Orchestration LLM
Groq (Llama 3.3 70B)            → Génération + réécriture de questions
Qdrant Cloud                     → Base vectorielle (documents indexés)
FastEmbed (MiniLM multilingue)  → Embeddings locaux, gratuit
Unstructured                     → Parsing documents multi-format
Supabase PostgreSQL              → Mémoire conversations + monitoring
Lakera Guard + regex             → Sécurité anti-injection
Edge TTS Henri Neural (fr-FR)   → Synthèse vocale
Railway                          → Déploiement cloud
```

---

## Tests — 77/77

```
test_generator.py       11 tests   génération LLM, reformulation questions
test_parser.py          11 tests   parsing tous les formats
test_document_loader.py  8 tests   chargement et détection fichiers
test_vector_store.py     8 tests   Qdrant (ajout, suppression, recherche)
test_tracker.py          9 tests   Supabase (mémoire + monitoring)
test_routes.py           9 tests   endpoints API, sécurité, streaming
test_chunker.py          7 tests   découpage des documents
test_run.py              7 tests   indexation, détection nouveaux fichiers
test_search.py           7 tests   recherche sémantique, déduplication
```

---

## Lancer le projet localement

```bash
git clone <repo>
cd Oracle-LoreKeeper
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # remplir les clés
python main.py         # http://localhost:5000
```

*Branche : `Emir` · Déployé sur Railway*
