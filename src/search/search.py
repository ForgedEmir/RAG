"""
Le coeur de notre moteur de recherche.
On utilise LangChain + Qdrant pour trouver les textes qui correspondent
semantiquement a la question posee.
"""
import logging
from typing import List, Tuple

from src.ingestion.vector_store import get_store, search

logger = logging.getLogger(__name__)


def rechercher_passages(question: str) -> Tuple[List[str], List[str]]:
    """
    On prend la question, on la convertit en vecteurs mathematiques
    et on la compare a tout ce qu'on a deja lu dans Qdrant.

    Retourne : (Le texte des meilleurs resultats, Le nom des fichiers d'origine)
    """
    store = get_store()

    # LangChain fait la recherche semantique via Qdrant.
    # On recupere les 3 documents les plus pertinents.
    results = search(store, question, k=3)

    # Extraction des textes et des sources depuis les Documents LangChain
    passages = [doc.page_content for doc in results]

    # On recolte les sources (nom du fichier) en evitant les doublons
    sources = []
    for doc in results:
        nom_fichier = doc.metadata.get("fichier", "inconnu")
        if nom_fichier not in sources:
            sources.append(nom_fichier)

    logger.info(f"Recherche pour '{question}' : {len(passages)} passage(s) trouve(s) dans nos archives.")

    return passages, sources
