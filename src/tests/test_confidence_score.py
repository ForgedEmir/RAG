"""Tests unitaires — Confidence Score (calcul et exposition SSE)."""
import pytest
from unittest.mock import MagicMock, patch


def test_rrf_retourne_scores():
    """_rrf doit retourner un tuple (docs, scores_dict)."""
    from src.search.search import _rrf

    vector = [{"id": "a", "text": "A", "filename": "f1"}, {"id": "b", "text": "B", "filename": "f2"}]
    bm25   = [{"id": "b", "text": "B", "filename": "f2"}, {"id": "c", "text": "C", "filename": "f3"}]

    docs, scores = _rrf(vector, bm25)

    assert isinstance(scores, dict)
    assert len(scores) == 3
    # "b" appears in both lists -> higher score
    assert scores["b"] > scores["a"] or scores["b"] > scores["c"]


@pytest.mark.asyncio
async def test_confidence_score_normalise():
    """Confidence scores returned by search_passages must be between 0 and 1."""
    with patch("src.search.search.get_store"), \
         patch("src.search.search.search", return_value=[
             MagicMock(page_content="Texte", metadata={"chunk_id": "c1", "filename": "f1"}),
         ]):
        from src.search.search import search_passages
        passages, sources, scores, *_ = await search_passages("Who is the Grand Master?")
        for s in scores:
            assert 0.0 <= s <= 1.0, f"Score hors plage : {s}"


@pytest.mark.asyncio
async def test_confidence_score_vide():
    """Without vector or BM25 results, search_passages returns empty lists."""
    with patch("src.search.search.get_store"), \
         patch("src.search.search.search", return_value=[]), \
         patch("src.search.search._bm25_index", None), \
         patch("src.search.search._bm25_corpus", []), \
         patch("src.search.search._bm25_loaded", True):
        from src.search.search import search_passages
        passages, sources, scores, *_ = await search_passages("question with no result xyz123")
        assert passages == []
        assert sources == []
        assert scores == []
