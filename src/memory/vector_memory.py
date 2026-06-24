"""Selective vector memory per user (Qdrant `user_memories`).
Enabled via VECTOR_MEMORY_ENABLED=true. Disabled by default.

Multi-tenant isolation: each memory point is tagged with tenant_id, and
search filter combines user_id + tenant_id so a user invited to multiple
tenants cannot leak memories across tenants.
"""
import logging
import os
import time
import uuid
from typing import List

from qdrant_client.models import (
    Distance, VectorParams,
    Filter, FieldCondition, MatchValue,
    PointStruct, PointIdsList, PayloadSchemaType,
)
from src.ingestion.vector_store import _get_client, _get_embeddings

logger = logging.getLogger(__name__)

_COLLECTION      = "user_memories"
_ENABLED         = os.getenv("VECTOR_MEMORY_ENABLED", "false").lower() != "false"
_MAX_MEMORIES    = int(os.getenv("MAX_USER_MEMORIES", "500"))
_ready           = False


def _ensure_collection() -> None:
    global _ready
    if _ready:
        return
    client = _get_client()
    vector_size = len(_get_embeddings().embed_query("dimension probe"))
    existing = [c.name for c in client.get_collections().collections]

    if _COLLECTION in existing:
        # Check existing dimension - recreate if mismatch
        info = client.get_collection(_COLLECTION)
        existing_dim = info.config.params.vectors.size
        if existing_dim != vector_size:
            logger.warning(
                f"Collection '{_COLLECTION}' : dimension mismatch "
                f"(existing={existing_dim}, model={vector_size}). Recreating."
            )
            client.delete_collection(_COLLECTION)
            existing = []  # Force recreation below

    if _COLLECTION not in existing:
        client.create_collection(
            collection_name=_COLLECTION,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info(f"Collection '{_COLLECTION}' created ({vector_size} dims).")

    # Index on user_id (existing) and tenant_id (new in multi-tenant mode)
    for field in ("user_id", "tenant_id"):
        try:
            client.create_payload_index(
                collection_name=_COLLECTION,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass
    _ready = True


def _user_filter(user_id: str, tenant_id: str = "") -> Filter:
    """Build a Qdrant filter for user memories.

    WHY: combine user_id AND tenant_id so a user invited to multiple tenants
    cannot retrieve memories stored under a different tenant. Previously only
    user_id was filtered, leaking cross-tenant content (T6 leak).
    """
    must = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    if tenant_id:
        must.append(FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)))
    return Filter(must=must)


def _trim(user_id: str, tenant_id: str = "") -> None:
    client = _get_client()
    uf = _user_filter(user_id, tenant_id)
    total = client.count(collection_name=_COLLECTION, count_filter=uf, exact=True).count
    if total <= _MAX_MEMORIES:
        return

    to_delete = total - _MAX_MEMORIES
    logger.info(f"Trim user memory '{user_id[:8]}...' (tenant={tenant_id or 'default'}): -{to_delete}")
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


def add_user_memory(user_id: str, question: str, answer: str, tenant_id: str = "") -> None:
    """Store a Q&A pair as a vector memory, scoped to (user_id, tenant_id).

    Args:
        user_id: The user's UUID.
        question: The question that was asked.
        answer: The generated answer.
        tenant_id: Tenant scope for multi-tenant isolation. CRITICAL: when a
                   user is invited to multiple tenants, memories from tenant X
                   must not be retrievable under tenant Y. Always pass the
                   caller's tenant_id.
    """
    if not _ENABLED or not user_id:
        return
    try:
        _ensure_collection()
        vector = _get_embeddings().embed_query(f"Q: {question}\nR: {answer[:300]}")
        _get_client().upsert(
            collection_name=_COLLECTION,
            points=[PointStruct(
                id=str(uuid.uuid4()), vector=vector,
                payload={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "question": question,
                    "answer": answer[:500],
                    "created_at": time.time(),
                },
            )],
        )
        _trim(user_id, tenant_id)
    except Exception as e:
        logger.warning(f"add_user_memory failed: {e}")


def search_user_memories(user_id: str, query: str, k: int = 3, tenant_id: str = "") -> List[str]:
    """Retrieve the k most similar memories for (user_id, tenant_id).

    Args:
        user_id: The user's UUID.
        query: The current question (used to find similar memories).
        k: Max number of memories to return.
        tenant_id: Tenant scope. CRITICAL: must match the tenant_id used when
                   storing the memory. A user invited to multiple tenants will
                   only retrieve memories stored under the given tenant_id.
    """
    if not _ENABLED or not user_id:
        return []
    try:
        _ensure_collection()
        vector = _get_embeddings().embed_query(query)
        response = _get_client().query_points(
            collection_name=_COLLECTION, query=vector,
            query_filter=_user_filter(user_id, tenant_id), limit=k, score_threshold=0.5,
        )
        return [f"- {h.payload.get('question','')} -> {h.payload.get('answer','')[:200]}" for h in response.points]
    except Exception as e:
        logger.warning(f"search_user_memories failed: {e}")
        return []
