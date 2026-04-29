"""HyDE (Hypothetical Document Embeddings) - Recall fallback.
When RRF scores are too low, generates a hypothetical answer via LLM,
embeds it, then searches for similar documents in Qdrant.

https://arxiv.org/abs/2212.10496
"""
import logging
import os
from typing import List

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

_HYDE_ENABLED = os.getenv("HYDE_ENABLED", "true").lower() != "false"

_HYDE_SYSTEM_PROMPT = (
    "Generate a hypothetical answer as if you knew the exact information "
    "about this fantasy lore topic. Only output the answer, 2-4 sentences."
)


def is_hyde_enabled() -> bool:
    return _HYDE_ENABLED


async def _hypothetical_answer(query: str) -> str:
    """Generates a hypothetical answer via the LLM already instantiated in generator.py."""
    try:
        from src.generation.generator import _llm_reformulation, _llm_fallback, _llm
        llm = _llm_reformulation or _llm_fallback or _llm
        if not llm:
            return ""
        result = await llm.ainvoke([
            SystemMessage(content=_HYDE_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])
        return result.content.strip()
    except Exception as e:
        logger.warning(f"HyDE LLM call failed: {e}")
        return ""


async def hyde_search(query: str, llm, embedder, qdrant, top_k: int = 3) -> List[Document]:
    """HyDE fallback: generates a hypothetical answer → embeds it → searches Qdrant.
    Triggered when RRF scores are too low to improve recall.
    """
    if not embedder or not qdrant:
        logger.warning("HyDE skipped: embedder or qdrant unavailable")
        return []

    hypothetical = await _hypothetical_answer(query)
    if not hypothetical:
        return []

    logger.info(f"HyDE rewriting query. Hypothetical: {hypothetical[:100]}...")
    try:
        # Note: embedder.embed_query is usually synchronous (local FastEmbed),
        # but qdrant.similarity_search_by_vector can be async if the store is.
        # Here we keep the call as is because get_store() returns a synchronous wrapper.
        emb = (list(embedder.embed([hypothetical]))[0]
               if hasattr(embedder, "embed")
               else embedder.embed_query(hypothetical))
        return qdrant.similarity_search_by_vector(emb, k=top_k)
    except Exception as e:
        logger.warning(f"HyDE vector search failed: {e}")
        return []
