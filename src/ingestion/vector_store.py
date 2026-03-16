"""
Le pont entre notre code et la base de donnees vectorielle (Qdrant).
Utilise LangChain + FastEmbed pour les embeddings multilingues (384 dims, local).

Qdrant supporte deux modes :
  - Local : stockage dans qdrant_db/ (aucun serveur externe)
  - Cloud : QDRANT_URL + QDRANT_API_KEY -> Qdrant Cloud
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

# ── Chemins / noms ─────────────────────────────────────────────────────────
_BASE_DIR        = os.path.dirname(__file__)
_DB_PATH         = os.path.join(_BASE_DIR, "qdrant_db")
_COLLECTION_NAME = "lore"
_VECTOR_SIZE     = 384  # MiniLM-L12-v2

# ── Qdrant Cloud ────────────────────────────────────────────────────────────
_QDRANT_URL     = os.getenv("QDRANT_URL")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# ── Singleton embeddings ────────────────────────────────────────────────────
_embeddings: Optional[FastEmbedEmbeddings] = None


def _get_embeddings() -> FastEmbedEmbeddings:
    """Retourne l'instance singleton des embeddings FastEmbed."""
    global _embeddings
    if _embeddings is None:
        model = os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        _embeddings = FastEmbedEmbeddings(model_name=model)
        logger.info(f"Embeddings FastEmbed charges : {model} ({_VECTOR_SIZE} dims)")
    return _embeddings


def _get_client() -> QdrantClient:
    """Retourne un client Qdrant Cloud ou local selon la configuration."""
    if _QDRANT_URL and _QDRANT_API_KEY:
        return QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY)
    return QdrantClient(path=_DB_PATH)


def _ensure_collection(client: QdrantClient) -> None:
    """Cree la collection 'lore' si elle n'existe pas encore."""
    collections = [c.name for c in client.get_collections().collections]
    if _COLLECTION_NAME not in collections:
        client.create_collection(
            collection_name=_COLLECTION_NAME,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info(f"Collection '{_COLLECTION_NAME}' creee (dims={_VECTOR_SIZE}).")


def get_store(force_reindex: bool = False) -> QdrantVectorStore:
    """
    Ouvre l'acces au coffre (notre collection 'lore') dans Qdrant.
    Si force_reindex est vrai, on vide la collection (cloud) ou le dossier local.
    """
    if force_reindex:
        if _QDRANT_URL and _QDRANT_API_KEY:
            temp_client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY)
            try:
                temp_client.delete_collection(_COLLECTION_NAME)
                logger.info(f"Collection '{_COLLECTION_NAME}' reinitalisee (mode cloud).")
            except Exception:
                pass
        elif os.path.exists(_DB_PATH):
            import shutil
            memory_file = os.path.join(_DB_PATH, "files_metadata.json")
            memory_backup = None
            if os.path.exists(memory_file):
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_backup = f.read()
            shutil.rmtree(_DB_PATH)
            logger.info("Ancienne base Qdrant supprimee. On fait place nette.")
            os.makedirs(_DB_PATH, exist_ok=True)
            if memory_backup:
                with open(memory_file, "w", encoding="utf-8") as f:
                    f.write(memory_backup)

    client = _get_client()
    _ensure_collection(client)

    return QdrantVectorStore(
        client=client,
        collection_name=_COLLECTION_NAME,
        embedding=_get_embeddings(),
    )


def add_documents(store: QdrantVectorStore, documents: List[Document]) -> None:
    """Ajoute une liste de Documents LangChain dans le vector store."""
    if not documents:
        return
    store.add_documents(documents)
    logger.info(f"{len(documents)} morceaux ont bien ete indexes dans Qdrant.")


def remove_files(store: QdrantVectorStore, fichiers: Set[str]) -> None:
    """Nettoie tous les fragments d'un ou plusieurs fichiers dans Qdrant."""
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
                                match=MatchValue(value=nom_fichier),
                            )
                        ]
                    )
                ),
            )
        except Exception as e:
            logger.warning(f"Impossible de supprimer les donnees de {nom_fichier}: {e}")
    logger.info(f"{len(fichiers)} fichier(s) nettoye(s) de Qdrant.")


def search(store: QdrantVectorStore, question: str, k: int = 3) -> List[Document]:
    """Recherche les k documents les plus similaires a la question."""
    return store.similarity_search(question, k=k)


def get_collection_stats() -> dict:
    """Retourne les statistiques de la collection Qdrant."""
    client = _get_client()
    _ensure_collection(client)
    try:
        info  = client.get_collection(_COLLECTION_NAME)
        total = client.count(_COLLECTION_NAME).count
        return {
            "total_vectors":   total,
            "collection_name": _COLLECTION_NAME,
            "status":          str(info.status),
            "mode":            "cloud" if (_QDRANT_URL and _QDRANT_API_KEY) else "local",
            "vector_size":     _VECTOR_SIZE,
        }
    except Exception as e:
        return {"error": str(e), "total_vectors": 0}


def count_chunks_by_file() -> dict:
    """Retourne un dictionnaire {nom_fichier: nb_chunks} pour tous les fichiers indexes."""
    client = _get_client()
    _ensure_collection(client)
    counts: dict = {}
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=_COLLECTION_NAME,
            with_payload=True,
            with_vectors=False,
            limit=500,
            offset=offset,
        )
        for point in points:
            nom = point.payload.get("metadata", {}).get("fichier", "inconnu")
            counts[nom] = counts.get(nom, 0) + 1
        if next_offset is None:
            break
        offset = next_offset
    return counts
