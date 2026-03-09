"""
Le pont entre notre code et la base de donnees vectorielle (Qdrant).
Ce module utilise LangChain pour abstraire les operations sur Qdrant.
Grace a cette abstraction, on pourrait switcher vers Pinecone, pgvector ou Weaviate
en changeant simplement quelques lignes ici.

Qdrant tourne en mode embarque (local) : pas besoin de serveur externe.
"""
import os
import logging
from typing import List, Set, Optional
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, FilterSelector, Filter, FieldCondition, MatchValue

logger = logging.getLogger(__name__)

# Chemin vers la base Qdrant locale (mode embarque, pas de serveur)
_BASE_DIR = os.path.dirname(__file__)
_DB_PATH = os.path.join(_BASE_DIR, "qdrant_db")

# Nom de la collection dans Qdrant
_COLLECTION_NAME = "lore"

# Dimension des vecteurs (384 pour le modele MiniLM-L12-v2)
_VECTOR_SIZE = 384

# Singleton : on garde une seule instance de l'embedding pour eviter de recharger le modele
_EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
_embeddings: Optional[FastEmbedEmbeddings] = None


def _get_embeddings() -> FastEmbedEmbeddings:
    """Retourne l'instance singleton des embeddings FastEmbed."""
    global _embeddings
    if _embeddings is None:
        _embeddings = FastEmbedEmbeddings(model_name=_EMBEDDING_MODEL)
    return _embeddings


def _ensure_collection(client: QdrantClient) -> None:
    """Cree la collection 'lore' si elle n'existe pas encore."""
    collections = [c.name for c in client.get_collections().collections]
    if _COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=_VECTOR_SIZE,
                distance=Distance.COSINE
            )
        )
        logger.info(f"Collection '{_COLLECTION_NAME}' creee dans Qdrant.")


def get_store(force_reindex: bool = False) -> QdrantVectorStore:
    """
    Ouvre l'acces au coffre (notre collection 'lore') dans Qdrant.
    Si force_reindex est vrai, on supprime physiquement le dossier qdrant_db pour repartir propre.
    """
    if force_reindex and os.path.exists(_DB_PATH):
        import shutil
        # On garde le fichier memory (files_metadata.json) s'il existe
        memory_file = os.path.join(_DB_PATH, "files_metadata.json")
        memory_backup = None
        if os.path.exists(memory_file):
            with open(memory_file, 'r', encoding='utf-8') as f:
                memory_backup = f.read()

        shutil.rmtree(_DB_PATH)
        logger.info("Ancienne base Qdrant supprimee. On fait place nette.")

        os.makedirs(_DB_PATH, exist_ok=True)
        if memory_backup:
            with open(memory_file, 'w', encoding='utf-8') as f:
                f.write(memory_backup)

    client = QdrantClient(path=_DB_PATH)
    _ensure_collection(client)

    return QdrantVectorStore(
        client=client,
        collection_name=_COLLECTION_NAME,
        embedding=_get_embeddings()
    )


def add_documents(store: QdrantVectorStore, documents: List[Document]) -> None:
    """
    Ajoute une liste de Documents LangChain dans le vector store.
    Chaque document a un page_content (texte) et des metadata (fichier source, etc.)
    """
    if not documents:
        return

    store.add_documents(documents)
    logger.info(f"{len(documents)} morceaux ont bien ete indexes dans Qdrant.")


def remove_files(store: QdrantVectorStore, fichiers: Set[str]) -> None:
    """
    Nettoie tous les paragraphes d'un ou plusieurs fichiers.
    Utilise le client Qdrant directement pour la suppression par filtre sur les metadonnees.
    """
    if not fichiers:
        return

    client = store.client

    for nom_fichier in fichiers:
        try:
            client.delete(
                collection_name=_COLLECTION_NAME,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="metadata.fichier",
                                match=MatchValue(value=nom_fichier)
                            )
                        ]
                    )
                )
            )
        except Exception as e:
            logger.warning(f"Impossible de supprimer les donnees de {nom_fichier}: {e}")

    logger.info(f"{len(fichiers)} fichier(s) nettoye(s) de Qdrant.")


def search(store: QdrantVectorStore, question: str, k: int = 3) -> List[Document]:
    """
    Recherche les k documents les plus similaires a la question.
    Retourne une liste de Documents LangChain avec page_content et metadata.
    """
    return store.similarity_search(question, k=k)
