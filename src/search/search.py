"""
Le cœur de notre moteur de recherche.
C'est ici qu'on va fouiller dans ChromaDB (qui stocke les paragraphes sous forme de vecteurs)
pour trouver les textes qui correspondent sémantiquement à la question posée.
"""
import logging
from typing import List, Tuple

from src.ingestion.loader import _get_collection

logger = logging.getLogger(__name__)


def rechercher_passages(question: str) -> Tuple[List[str], List[str]]:
    """
    On prend la question, on la convertit en mots clés/vecteurs mathématiques
    et on la compare à tout ce qu'on a déjà lu.
    
    Retourne : (Le texte des meilleurs résultats, Le nom des fichiers d'origine)
    """
    collection = _get_collection()

    # ChromaDB fait la mathématique de comparaison ('embeddings') en arrière-plan.
    # On lui demande de nous ramener strictement les 3 meilleurs "paragraphes".
    results = collection.query(
        query_texts=[question],
        n_results=3
    )

    # Récupération de la liste des textes qu'on a matchés
    documents = results.get("documents", [[]])
    passages = documents[0] if documents else []

    # On récolte aussi les métadonnées (nom du fichier) pour pouvoir dire "d'après tel document..."
    metadatas = results.get("metadatas", [[]])
    sources = []
    if metadatas and metadatas[0]:
        for meta in metadatas[0]:
            nom_fichier = meta.get("fichier", "inconnu")
            # Éviter les doublons de source si on a deux paragraphes du même fichier
            if nom_fichier not in sources:
                sources.append(nom_fichier)

    logger.info(f"Recherche pour '{question}' : {len(passages)} passage(s) trouvé(s) dans nos archives.")

    return passages, sources