"""Feature flags and runtime profiles for Oracle LoreKeeper.

`RAG_FAST_MODE=true` applies conservative defaults focused on lower latency
without overriding explicitly configured environment variables.
"""
import os
from typing import Dict

_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_PROFILE_APPLIED = False

_PROFILES = {
    "fast": {
        "RERANKER_ENABLED": "false",
        "RERANK_SIMPLE_QUERIES": "false",
        "SMART_RERANK_ENABLED": "false",
        "QUERY_EXPANSION_ENABLED": "false",
        "REFORMULATION_ENABLED": "false",
        "VECTOR_MEMORY_ENABLED": "false",
        "HYDE_ENABLED": "false",
        "SECURITY_VALIDATOR": "true",
        "INGESTION_LORE_CLASSIFIER_ENABLED": "false",
        "INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED": "false",
        "WATCHDOG_ENABLED": "false",
    },
    "balanced": {
        "RERANKER_ENABLED": "true",
        "RERANK_SIMPLE_QUERIES": "false",
        "SMART_RERANK_ENABLED": "true",
        "QUERY_EXPANSION_ENABLED": "false",
        "REFORMULATION_ENABLED": "true",
        "VECTOR_MEMORY_ENABLED": "false",
        "HYDE_ENABLED": "true",
        "SECURITY_VALIDATOR": "true",
        "INGESTION_LORE_CLASSIFIER_ENABLED": "false",
        "INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED": "true",
        "WATCHDOG_ENABLED": "true",
    },
    "quality": {
        "RERANKER_ENABLED": "true",
        "RERANK_SIMPLE_QUERIES": "true",
        "SMART_RERANK_ENABLED": "false",
        "QUERY_EXPANSION_ENABLED": "true",
        "REFORMULATION_ENABLED": "true",
        "VECTOR_MEMORY_ENABLED": "true",
        "HYDE_ENABLED": "true",
        "SECURITY_VALIDATOR": "true",
        "INGESTION_LORE_CLASSIFIER_ENABLED": "true",
        "INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED": "true",
        "WATCHDOG_ENABLED": "true",
    },
}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in _FALSE_VALUES


def apply_feature_profile() -> Dict[str, bool]:
    """Apply startup profile defaults exactly once.

    Uses `setdefault` so explicit env values always win.
    """
    global _PROFILE_APPLIED
    if _PROFILE_APPLIED:
        return get_runtime_profile()

    profile = (os.getenv("RAG_PROFILE", "balanced") or "balanced").strip().lower()
    if env_bool("RAG_FAST_MODE", False):
        profile = "fast"

    defaults = _PROFILES.get(profile, _PROFILES["balanced"])
    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    os.environ.setdefault("RAG_PROFILE", profile if profile in _PROFILES else "balanced")

    _PROFILE_APPLIED = True
    return get_runtime_profile()


def get_runtime_profile() -> Dict[str, bool]:
    return {
        "rag_fast_mode": env_bool("RAG_FAST_MODE", False),
        "rag_profile": os.getenv("RAG_PROFILE", "balanced"),
        "reranker_enabled": env_bool("RERANKER_ENABLED", True),
        "query_expansion_enabled": env_bool("QUERY_EXPANSION_ENABLED", False),
        "reformulation_enabled": env_bool("REFORMULATION_ENABLED", True),
        "vector_memory_enabled": env_bool("VECTOR_MEMORY_ENABLED", False),
        "hyde_enabled": env_bool("HYDE_ENABLED", True),
        "watchdog_enabled": env_bool("WATCHDOG_ENABLED", True),
    }
