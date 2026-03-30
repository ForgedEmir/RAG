"""
Configuration pytest partagée.
Remet à zéro l'état des modules (cache, BM25, rate limiter) avant chaque test
pour éviter les interférences entre tests.
"""
import pytest
import src.search.search as search_module


@pytest.fixture(autouse=True)
def reset_search_state():
    """Vide le cache, réinitialise BM25 et le rate limiter avant chaque test."""
    search_module._search_cache.clear()
    search_module._bm25_loaded = False
    search_module._bm25_index = None
    search_module._bm25_corpus = []
    try:
        from src.api.limiter import limiter
        limiter._storage.reset()
    except Exception:
        pass
    yield
    search_module._search_cache.clear()
