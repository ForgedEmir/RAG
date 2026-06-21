"""
Shared pytest configuration.
Resets module state (cache, BM25, rate limiter) before each test
to avoid interference between tests.
"""
import pytest
import src.search.search as search_module


@pytest.fixture(autouse=True)
def reset_search_state():
    """Resets BM25, rate limiter, semantic cache, and constants before each test."""
    search_module._bm25_loaded = False
    search_module._bm25_index = None
    search_module._bm25_corpus = []
    
    # Semantic cache reset (Redis or Mock)
    try:
        import asyncio
        from src.caching.semantic_cache import clear_all
        try:
            asyncio.run(clear_all())
        except RuntimeError:
            # Already in a loop, unlikely here but fail-safe
            pass
    except Exception:
        pass

    # Save and restore mutable constants (patched by some tests)
    original_hyde_threshold = search_module._HYDE_THRESHOLD
    original_reranker_enabled = search_module._RERANKER_ENABLED
    try:
        from src.api.limiter import limiter
        limiter._storage.reset()
    except Exception:
        pass
    yield
    search_module._HYDE_THRESHOLD = original_hyde_threshold
    search_module._RERANKER_ENABLED = original_reranker_enabled
