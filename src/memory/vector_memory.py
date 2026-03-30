"""Mémoire vectorielle sélective par utilisateur (Qdrant `user_memories`).
Activée via VECTOR_MEMORY_ENABLED=true. Désactivée par défaut.
"""
import logging
import os
import time
import uuid
from typing import List

from qdrant_client.models import (
    Distance, VectorParams,
    Filter, FieldCondition, MatchValue,
    PointStruct, PointIdsList,
)
from src.ingestion.vector_store import _get_client, _get_embeddings

logger = logging.getLogger(__name__)

_COLLECTION      = "user_memories"
_VECTOR_SIZE     = 1024  # BGE-M3
_ENABLED         = os.getenv("VECTOR_MEMORY_ENABLED", "false").lower() != "false"
_MAX_MEMORIES    = int(os.getenv("MAX_USER_MEMORIES", "500"))
_ready           = False


def _ensure_collection() -> None:
    global _ready
    if _ready:
        return
    client = _get_client()
    if _COLLECTION not in [c.name for c in client.get_collections().collections]:
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
        )
        logger.info(f"Collection '{_COLLECTION}' créée.")
    _ready = True


def _user_filter(user_id: str) -> Filter:
    return Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])


def _trim(user_id: str) -> None:
    client = _get_client()
    uf = _user_filter(user_id)
    total = client.count(collection_name=_COLLECTION, count_filter=uf, exact=True).count
    if total <= _MAX_MEMORIES:
        return

    to_delete = total - _MAX_MEMORIES
    logger.info(f"Trim mémoire user '{user_id[:8]}…' : -{to_delete}")
    try:
        from qdrant_client.models import OrderBy
        points, _ = client.scroll(
            collection_name=_COLLECTION, scroll_filter=uf,
            limit=to_delete, order_by=OrderBy(key="created_at", direction="asc"),
            with_payload=False, with_vectors=False,
        )
    except Exception:
        points, _ = client.scroll(
            collection_name=_COLLECTION, scroll_filter=uf,
            limit=total, with_payload=True, with_vectors=False,
        )
        points = sorted(points, key=lambda p: p.payload.get("created_at", 0))[:to_delete]

    client.delete(collection_name=_COLLECTION, points_selector=PointIdsList(points=[p.id for p in points]))


def add_user_memory(user_id: str, question: str, answer: str) -> None:
    if not _ENABLED or not user_id:
        return
    try:
        _ensure_collection()
        vector = _get_embeddings().embed_query(f"Q: {question}\nR: {answer[:300]}")
        _get_client().upsert(
            collection_name=_COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()), vector=vector,
                payload={"user_id": user_id, "question": question,
                         "answer": answer[:500], "created_at": time.time()},
            )],
        )
        _trim(user_id)
    except Exception as e:
        logger.warning(f"add_user_memory échoué : {e}")


def search_user_memories(user_id: str, query: str, k: int = 3) -> List[str]:
    if not _ENABLED or not user_id:
        return []
    try:
        _ensure_collection()
        vector = _get_embeddings().embed_query(query)
        results = _get_client().search(
            collection_name=_COLLECTION, query_vector=vector,
            query_filter=_user_filter(user_id), limit=k, score_threshold=0.5,
        )
        return [f"- {h.payload.get('question','')} → {h.payload.get('answer','')[:200]}" for h in results]
    except Exception as e:
        logger.warning(f"search_user_memories échoué : {e}")
        return []
