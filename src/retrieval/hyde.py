"""HyDE (Hypothetical Document Embeddings) - Fallback de rappel.
Quand les scores RRF sont trop bas, génère une réponse hypothétique via LLM,
l'embarque, puis cherche des documents similaires dans Qdrant.

https://arxiv.org/abs/2212.10496
"""
import logging
import os
from typing import List

import httpx
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

_HYDE_ENABLED = os.getenv("HYDE_ENABLED", "true").lower() != "false"
_HYDE_CHEAP_MODEL = os.getenv("HYDE_CHEAP_MODEL", "meta-llama/llama-3.2-3b-instruct")
_HYDE_TIMEOUT_SECONDS = float(os.getenv("HYDE_TIMEOUT_SECONDS", "3.5"))
_HYDE_API_URL = os.getenv("HYDE_API_URL", "https://openrouter.ai/api/v1/chat/completions")


def is_hyde_enabled() -> bool:
    return _HYDE_ENABLED


def _hypothetical_answer(query: str) -> str:
    """Génère une réponse hypothétique via httpx + OpenRouter (modèle cheap)."""
    api_key = os.getenv("HYDE_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        return ""
    try:
        with httpx.Client(timeout=_HYDE_TIMEOUT_SECONDS) as client:
            resp = client.post(
                _HYDE_API_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": _HYDE_CHEAP_MODEL,
                    "messages": [
                        {"role": "system", "content": (
                            "Generate a hypothetical answer as if you knew the exact information "
                            "about this fantasy lore topic. Only output the answer, 2-4 sentences."
                        )},
                        {"role": "user", "content": query}
                    ],
                    "max_tokens": 256
                }
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"HyDE httpx call failed: {e}")
        return ""


def hyde_search(query: str, llm, embedder, qdrant, top_k: int = 3) -> List[Document]:
    """HyDE fallback : génère une réponse hypothétique → l'embarque → cherche dans Qdrant.
    Déclenché quand les scores RRF sont trop bas pour améliorer le rappel.
    """
    if not embedder or not qdrant:
        logger.warning("HyDE skipped: embedder or qdrant unavailable")
        return []

    hypothetical = _hypothetical_answer(query)
    if not hypothetical:
        return []

    logger.info(f"HyDE rewriting query. Hypothetical: {hypothetical[:100]}...")
    try:
        emb = (list(embedder.embed([hypothetical]))[0]
               if hasattr(embedder, "embed")
               else embedder.embed_query(hypothetical))
        return qdrant.similarity_search_by_vector(emb, k=top_k)
    except Exception as e:
        logger.warning(f"HyDE vector search failed: {e}")
        return []
