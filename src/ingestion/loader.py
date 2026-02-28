"""
Module loader : gère les interactions avec la base de données ChromaDB.
Permet d'ajouter, de stocker et de supprimer des textes dans la base.
"""
import os
import hashlib
import logging
import chromadb
from chromadb.utils import embedding_functions
from typing import Any, List

# Créer un logger pour ce module
logger = logging.getLogger(__name__)

# Modèle d'embedding multilingue (supporte le français, anglais, etc.)
# Le modèle par défaut de ChromaDB (all-MiniLM-L6-v2) ne comprend que l'anglais
EMBEDDING_FUNCTION = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)


def _get_collection(force_reindex: bool = False) -> Any:
    """
    Récupère (ou crée) la collection 'lore' dans ChromaDB.
    Si force_reindex=True, supprime l'ancienne collection pour repartir de zéro.
    """
    base_dir = os.path.dirname(__file__)
    db_path = os.path.join(base_dir, "chroma_db")

    # Se connecter à la base de données locale
    client = chromadb.PersistentClient(path=db_path)

    # Si on force la réindexation, on supprime l'ancienne collection
    if force_reindex:
        try:
            client.delete_collection("lore")
            logger.info("Ancienne collection supprimée.")
        except Exception:
            pass

    # Récupérer ou créer la collection "lore" avec le modèle multilingue
    return client.get_or_create_collection("lore", embedding_function=EMBEDDING_FUNCTION)


def store_in_chromadb(chunks: List[dict], force_reindex: bool = False) -> Any:
    """
    Crée la collection et y stocke tous les morceaux de texte.
    Utilisé lors d'une réindexation complète.
    """
    collection = _get_collection(force_reindex)
    add_to_chromadb(collection, chunks)
    return collection


def add_to_chromadb(collection: Any, chunks: List[dict]) -> None:
    """
    Ajoute des morceaux de texte dans la base de données ChromaDB.
    Chaque morceau reçoit un identifiant unique basé sur son contenu.
    """
    if not chunks:
        return

    ids = []
    textes = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        # Créer un identifiant unique à partir du contenu du texte
        text_hash = hashlib.md5(chunk["texte"].encode('utf-8')).hexdigest()[:16]
        unique_id = f"{chunk['fichier']}_{i}_{text_hash}"

        ids.append(unique_id)
        textes.append(chunk["texte"])
        metadatas.append({"fichier": chunk["fichier"]})

    # Insérer tout d'un coup dans la base
    collection.add(ids=ids, documents=textes, metadatas=metadatas)
    logger.info(f"{len(chunks)} morceaux ajoutés à la base de données.")


def remove_files_from_chromadb(collection: Any, fichiers: set) -> None:
    """
    Supprime de la base tous les morceaux liés aux fichiers donnés.
    Utile quand un fichier a été modifié ou supprimé.
    """
    if not fichiers:
        return

    for nom_fichier in fichiers:
        collection.delete(where={"fichier": nom_fichier})

    logger.info(f"{len(fichiers)} fichier(s) nettoyé(s) de la base.")