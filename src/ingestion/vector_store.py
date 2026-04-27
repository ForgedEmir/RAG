"""Interface Qdrant : connexion, indexation, recherche.
Cloud (QDRANT_URL + QDRANT_API_KEY) ou local (qdrant_db/).
"""
import os
import logging
import re
import shutil
import threading
from typing import List, Set, Optional

from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings
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
_QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH = os.getenv(
    "QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH", "true"
).lower() != "false"
_QDRANT_VECTOR_SIZE_OVERRIDE = os.getenv("QDRANT_VECTOR_SIZE")
_FASTEMBED_CACHE_PATH = os.getenv("FASTEMBED_CACHE_PATH", "/tmp/fastembed_cache")

# Singletons — créés une seule fois
_embeddings: Optional[FastEmbedEmbeddings] = None
_client: Optional[QdrantClient] = None
_collection_ready: bool = False
_vector_size: Optional[int] = None
_embeddings_lock = threading.Lock()


def _is_fastembed_cache_missing_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "no such file or directory" in msg
        and ("model.onnx_data" in msg or "fastembed_cache" in msg or "onnx" in msg)
    )


def _extract_missing_path(exc: Exception) -> Optional[str]:
    msg = str(exc)
    match = re.search(r"no such file or directory\s*\[([^\]]+)\]", msg, flags=re.IGNORECASE)
    if not match:
        return None
    return os.path.normpath(match.group(1))


def _purge_corrupted_fastembed_cache(exc: Exception, model_name: str) -> None:
    """Supprime les dossiers cache FastEmbed incomplets pour permettre un retry propre."""
    model_leaf = model_name.split("/")[-1]
    targets = {
        os.path.join(_FASTEMBED_CACHE_PATH, f"models--qdrant--{model_leaf}-onnx"),
        os.path.join(_FASTEMBED_CACHE_PATH, f"models--qdrant--{model_leaf}"),
    }

    missing_path = _extract_missing_path(exc)
    if missing_path and "snapshots" in missing_path:
        snapshot_parent = os.path.dirname(os.path.dirname(missing_path))
        model_root = os.path.dirname(snapshot_parent)
        targets.add(model_root)

    removed = 0
    for target in targets:
        if os.path.isdir(target):
            try:
                shutil.rmtree(target)
                removed += 1
            except Exception as e:
                logger.warning("Purge cache FastEmbed impossible (%s): %s", target, e)

    if removed:
        logger.warning("Cache FastEmbed corrompu détecté: %s dossier(s) purgé(s).", removed)


def _get_embeddings() -> FastEmbedEmbeddings:
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    with _embeddings_lock:
        if _embeddings is not None:
            return _embeddings

        model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        os.makedirs(_FASTEMBED_CACHE_PATH, exist_ok=True)

        def _build() -> FastEmbedEmbeddings:
            # FastEmbed uses ONNX — no PyTorch/GPU required.
            return FastEmbedEmbeddings(model_name=model, cache_dir=_FASTEMBED_CACHE_PATH)

        try:
            _embeddings = _build()
            logger.info(f"FastEmbed embeddings chargé : {model}")
            return _embeddings
        except Exception as e:
            if not _is_fastembed_cache_missing_error(e):
                raise

            logger.warning("FastEmbed init échoué (cache incomplet), purge + retry en cours.")
            _purge_corrupted_fastembed_cache(e, model)
            _embeddings = _build()
            logger.info(f"FastEmbed embeddings chargé après purge cache : {model}")
            return _embeddings


def _get_vector_size() -> int:
    global _vector_size
    if _vector_size is None:
        probe = _get_embeddings().embed_query("dimension probe")
        _vector_size = len(probe)
    return _vector_size


def _get_expected_vector_size() -> int:
    """Expected collection dimension from override or embedding model."""
    if _QDRANT_VECTOR_SIZE_OVERRIDE:
        try:
            value = int(_QDRANT_VECTOR_SIZE_OVERRIDE)
            if value > 0:
                return value
        except ValueError:
            logger.warning("QDRANT_VECTOR_SIZE invalide (%s), fallback embedder.", _QDRANT_VECTOR_SIZE_OVERRIDE)
    return _get_vector_size()


def _collection_vector_size(client: QdrantClient) -> int:
    info = client.get_collection(_COLLECTION_NAME)
    vectors = info.config.params.vectors
    if hasattr(vectors, "size"):
        return int(vectors.size)
    if isinstance(vectors, dict):
        first = next(iter(vectors.values()), None)
        if first is not None and hasattr(first, "size"):
            return int(first.size)
    raise ValueError("Impossible de lire la dimension de la collection Qdrant.")


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
    expected_size = _get_expected_vector_size()

    if _COLLECTION_NAME in existing:
        try:
            current_size = _collection_vector_size(client)
            if current_size != expected_size:
                message = (
                    f"Qdrant dimension mismatch: collection={current_size}, expected={expected_size}."
                )
                if _QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH:
                    logger.warning("%s Recréation automatique activée.", message)
                    client.delete_collection(_COLLECTION_NAME)
                    existing.remove(_COLLECTION_NAME)
                else:
                    raise RuntimeError(message)
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            logger.warning("Vérification dimension Qdrant impossible: %s", e)

    if _COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=_COLLECTION_NAME,
            vectors_config=VectorParams(size=expected_size, distance=Distance.COSINE),
        )
        logger.info(f"Collection '{_COLLECTION_NAME}' créée ({expected_size} dims).")

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
    try:
        return QdrantVectorStore(client=client, collection_name=_COLLECTION_NAME, embedding=_get_embeddings())
    except Exception as e:
        if "dimensions" not in str(e).lower() and "vector" not in str(e).lower():
            raise
        logger.warning(f"Dimension mismatch détectée, réinitialisation de la collection : {e}")
        client.delete_collection(_COLLECTION_NAME)
        _collection_ready = False
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
