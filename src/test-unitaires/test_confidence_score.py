"""Tests unitaires — Confidence Score (calcul et exposition SSE)."""
import pytest
from unittest.mock import MagicMock, patch


def test_rrf_retourne_scores():
    """_rrf doit retourner un tuple (docs, scores_dict)."""
    from src.search.search import _rrf

    vector = [{"id": "a", "text": "A", "fichier": "f1"}, {"id": "b", "text": "B", "fichier": "f2"}]
    bm25   = [{"id": "b", "text": "B", "fichier": "f2"}, {"id": "c", "text": "C", "fichier": "f3"}]

    docs, scores = _rrf(vector, bm25)

    assert isinstance(scores, dict)
    assert len(scores) == 3
    # "b" apparaît dans les deux listes → score plus élevé
    assert scores["b"] > scores["a"] or scores["b"] > scores["c"]


@pytest.mark.asyncio
async def test_confidence_score_normalise():
    """Les scores de confiance retournés par rechercher_passages doivent être entre 0 et 1."""
    with patch("src.search.search.get_store"), \
         patch("src.search.search.search", return_value=[
             MagicMock(page_content="Texte", metadata={"chunk_id": "c1", "fichier": "f1"}),
         ]):
        from src.search.search import rechercher_passages
        passages, sources, scores, *_ = await rechercher_passages("Qui est le Grand Maître ?")
        for s in scores:
            assert 0.0 <= s <= 1.0, f"Score hors plage : {s}"


@pytest.mark.asyncio
async def test_confidence_score_vide():
    """Sans résultats vecteurs ni BM25, rechercher_passages retourne des listes vides."""
    with patch("src.search.search.get_store"), \
         patch("src.search.search.search", return_value=[]), \
         patch("src.search.search._bm25_index", None), \
         patch("src.search.search._bm25_corpus", []), \
         patch("src.search.search._bm25_loaded", True):
        from src.search.search import rechercher_passages
        passages, sources, scores, *_ = await rechercher_passages("question sans résultat xyz123")
        assert passages == []
        assert sources == []
        assert scores == []
