"""
Module de recherche : interroge la base de données vectorielle ChromaDB
pour trouver les passages de texte les plus proches de la question posée.
"""
import os
import logging
import chromadb
from typing import List, Tuple

# Créer un logger pour ce module
logger = logging.getLogger(__name__)

# --- Client ChromaDB créé une seule fois (singleton) ---
# Évite de reconnecter la base à chaque question posée
_base_dir = os.path.dirname(__file__)
_db_path = os.path.normpath(os.path.join(_base_dir, "..", "ingestion", "chroma_db"))
_client_db = chromadb.PersistentClient(path=_db_path)


def rechercher_passages(question: str) -> Tuple[List[str], List[str]]:
    """
    Cherche les 3 passages les plus pertinents dans la base de données.

    Args:
        question : la question posée par l'utilisateur

    Returns:
        Un tuple (liste de passages trouvés, liste des fichiers sources)
    """
    collection = _client_db.get_or_create_collection(name="lore")

    # Lancer la recherche par similarité (ChromaDB compare les vecteurs automatiquement)
    results = collection.query(
        query_texts=[question],
        n_results=3
    )

    # Extraire les documents trouvés
    documents = results.get("documents", [[]])
    passages = documents[0] if documents else []

    # Extraire les noms de fichiers sources (pour citer d'où vient l'info)
    metadatas = results.get("metadatas", [[]])
    sources = []
    if metadatas and metadatas[0]:
        for meta in metadatas[0]:
            nom_fichier = meta.get("fichier", "inconnu")
            if nom_fichier not in sources:
                sources.append(nom_fichier)

    logger.info(f"Recherche pour '{question}' : {len(passages)} passage(s) trouvé(s) depuis {sources}")

    return passages, sources