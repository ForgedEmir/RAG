"""Interface Qdrant : connexion, indexation, recherche.
Cloud (QDRANT_URL + QDRANT_API_KEY) ou local (qdrant_db/).
"""
import os
import logging
import shutil
from typing import List, Set, Optional

from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    FilterSelector,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)

logger = logging.getLogger(__name__)

_BASE_DIR        = os.path.dirname(__file__)
_DB_PATH         = os.path.join(_BASE_DIR, "qdrant_db")
_COLLECTION_NAME = "lore"

_QDRANT_URL     = os.getenv("QDRANT_URL")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Singletons — créés une seule fois
_embeddings: Optional[HuggingFaceEmbeddings] = None
_client: Optional[QdrantClient] = None
_collection_ready: bool = False
_vector_size: Optional[int] = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        _embeddings = HuggingFaceEmbeddings(
            model_name=model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        logger.info(f"Modèle d'embeddings chargé : {model}")
    return _embeddings


def _get_vector_size() -> int:
    global _vector_size
    if _vector_size is None:
        probe = _get_embeddings().embed_query("dimension probe")
        _vector_size = len(probe)
    return _vector_size


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        if _QDRANT_URL:
            _client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY or None)
            logger.info(f"Qdrant connecté : {_QDRANT_URL}")
        else:
            _client = QdrantClient(path=_DB_PATH)
            logger.info("Qdrant local (mode développement)")
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    """Crée la collection 'lore' si elle n'existe pas encore."""
    global _collection_ready
    if _collection_ready:
        return
    existing = [c.name for c in client.get_collections().collections]
    if _COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=_COLLECTION_NAME,
            vectors_config=VectorParams(size=_get_vector_size(), distance=Distance.COSINE),
        )
        logger.info(f"Collection '{_COLLECTION_NAME}' créée.")

    # Requis pour les filtres de suppression sur metadata.fichier.
    try:
        client.create_payload_index(
            collection_name=_COLLECTION_NAME,
            field_name="metadata.fichier",
            field_schema=PayloadSchemaType.KEYWORD,
        )
    except Exception as e:
        logger.debug(f"Index payload metadata.fichier déjà présent ou non créé: {e}")

    _collection_ready = True


def get_store(force_reindex: bool = False) -> QdrantVectorStore:
    """Retourne le vector store Qdrant.
    Si force_reindex=True, supprime et recrée la collection.
    """
    global _client, _collection_ready

    if force_reindex:
        _client = None
        _collection_ready = False
        if _QDRANT_URL:
            temp = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY or None)
            try:
                temp.delete_collection(_COLLECTION_NAME)
                logger.info("Collection réinitialisée (cloud).")
            except Exception as e:
                logger.warning(f"Impossible de supprimer la collection cloud : {e}")
        elif os.path.exists(_DB_PATH):
            # Sauvegarde le fichier mémoire avant de tout supprimer
            memory_file = os.path.join(_DB_PATH, "files_metadata.json")
            backup = None
            if os.path.exists(memory_file):
                with open(memory_file, "r", encoding="utf-8") as f:
                    backup = f.read()
            shutil.rmtree(_DB_PATH)
            os.makedirs(_DB_PATH, exist_ok=True)
            if backup:
                with open(memory_file, "w", encoding="utf-8") as f:
                    f.write(backup)
            logger.info("Base locale supprimée et recréée.")

    client = _get_client()
    _ensure_collection(client)
    return QdrantVectorStore(client=client, collection_name=_COLLECTION_NAME, embedding=_get_embeddings())


def add_documents(store: QdrantVectorStore, documents: List[Document]) -> None:
    """Ajoute des documents dans Qdrant."""
    if not documents:
        return
    store.add_documents(documents)
    logger.info(f"{len(documents)} documents indexés.")


def remove_files(store: QdrantVectorStore, fichiers: Set[str]) -> None:
    """Supprime tous les chunks associés à une liste de fichiers."""
    if not fichiers:
        return
    try:
        store.client.delete(
            collection_name=_COLLECTION_NAME,
            points_selector=FilterSelector(
                filter=Filter(should=[
                    FieldCondition(key="metadata.fichier", match=MatchValue(value=nom))
                    for nom in fichiers
                ])
            ),
        )
        logger.info(f"{len(fichiers)} fichier(s) retiré(s) de Qdrant.")
    except Exception as e:
        logger.warning(f"Impossible de supprimer les fichiers : {e}")


def search(store: QdrantVectorStore, question: str, k: int = 3) -> List[Document]:
    """Recherche les k documents les plus proches de la question."""
    return store.similarity_search(question, k=k)
