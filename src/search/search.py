"""
Moteur de recherche sémantique.
Convertit une question en vecteurs et trouve les passages les plus pertinents dans Qdrant.
"""
import logging
from typing import List, Tuple

from src.ingestion.vector_store import get_store, search

logger = logging.getLogger(__name__)


def rechercher_passages(question: str) -> Tuple[List[str], List[str]]:
    """
    Cherche les 5 passages les plus proches de la question dans Qdrant.
    Retourne (textes des passages, noms des fichiers sources).
    """
    store = get_store()
    results = search(store, question, k=5)

    passages = [doc.page_content for doc in results]
    sources = list(dict.fromkeys(doc.metadata.get("fichier", "inconnu") for doc in results))

    logger.info(f"'{question}' → {len(passages)} passage(s) trouvé(s).")
    return passages, sources
