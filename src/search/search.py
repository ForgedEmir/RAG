"""
Recherche hybride : combine recherche vectorielle (Qdrant) + BM25 (texte brut).
Les résultats sont fusionnés via Reciprocal Rank Fusion (RRF).
"""
import json
import logging
import os
from typing import List, Tuple, Optional

from rank_bm25 import BM25Okapi
from src.ingestion.vector_store import get_store, search

logger = logging.getLogger(__name__)

_BM25_CORPUS_FILE = os.path.join(os.path.dirname(__file__), "..", "ingestion", "qdrant_db", "bm25_corpus.json")

# Cache BM25 en mémoire (reconstruit au premier appel ou après réindexation)
_bm25_index: Optional[BM25Okapi] = None
_bm25_corpus: List[dict] = []
_bm25_loaded: bool = False


def _load_bm25():
    """Charge le corpus BM25 depuis le JSON et construit l'index."""
    global _bm25_index, _bm25_corpus, _bm25_loaded
    path = os.path.normpath(_BM25_CORPUS_FILE)
    if not os.path.exists(path):
        logger.warning("Corpus BM25 introuvable — hybrid search désactivée, vector-only.")
        _bm25_index = None
        _bm25_corpus = []
        _bm25_loaded = True
        return

    with open(path, "r", encoding="utf-8") as f:
        _bm25_corpus = json.load(f)

    if not _bm25_corpus:
        _bm25_index = None
        _bm25_loaded = True
        return

    tokenized = [doc["text"].lower().split() for doc in _bm25_corpus]
    _bm25_index = BM25Okapi(tokenized)
    _bm25_loaded = True
    logger.info(f"Index BM25 chargé ({len(_bm25_corpus)} chunks).")


def invalidate_bm25_cache():
    """Force le rechargement du BM25 au prochain appel (après réindexation)."""
    global _bm25_loaded
    _bm25_loaded = False


def _rrf_fusion(vector_results: List[dict], bm25_results: List[dict], k: int = 60) -> List[dict]:
    """Reciprocal Rank Fusion — fusionne deux listes de résultats rankés."""
    scores = {}
    doc_map = {}

    for rank, doc in enumerate(vector_results):
        key = doc["text"][:200]  # clé de déduplication
        scores[key] = scores.get(key, 0) + 1 / (k + rank)
        doc_map[key] = doc

    for rank, doc in enumerate(bm25_results):
        key = doc["text"][:200]
        scores[key] = scores.get(key, 0) + 1 / (k + rank)
        doc_map[key] = doc

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [doc_map[key] for key in sorted_keys]


def rechercher_passages(question: str) -> Tuple[List[str], List[str]]:
    """Recherche hybride : vectorielle (Qdrant) + BM25, fusionnées via RRF.
    Retourne (textes des passages, noms des fichiers sources).
    """
    # 1. Recherche vectorielle
    store = get_store()
    vector_docs = search(store, question, k=5)
    vector_results = [
        {"text": doc.page_content, "fichier": doc.metadata.get("fichier", "inconnu")}
        for doc in vector_docs
    ]

    # 2. Recherche BM25
    if not _bm25_loaded:
        _load_bm25()

    if _bm25_index and _bm25_corpus:
        tokenized_query = question.lower().split()
        bm25_scores = _bm25_index.get_scores(tokenized_query)
        top_indices = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:5]
        bm25_results = [_bm25_corpus[i] for i in top_indices if bm25_scores[i] > 0]
    else:
        bm25_results = []

    # 3. Fusion RRF
    if bm25_results:
        combined = _rrf_fusion(vector_results, bm25_results)[:5]
    else:
        combined = vector_results

    passages = [doc["text"] for doc in combined]
    sources = list(dict.fromkeys(doc["fichier"] for doc in combined))

    logger.info(f"'{question}' → {len(passages)} passage(s) (vector:{len(vector_results)}, bm25:{len(bm25_results)}).")
    return passages, sources
