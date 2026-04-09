"""Tests unitaires pour le judge local (score global + métriques)."""

from unittest.mock import Mock, patch

from src.security.judge import _parse_multi_scores, evaluer_reponse, evaluer_reponse_multi


def test_parse_multi_scores_json_markdown_ok():
    raw = """```json
    {"context_relevance": 0.9, "faithfulness": 0.8, "answer_relevance": 0.7, "context_coverage": 0.6}
    ```"""
    parsed = _parse_multi_scores(raw)
    assert parsed is not None
    assert parsed["context_relevance"] == 0.9
    assert parsed["faithfulness"] == 0.8
    assert parsed["answer_relevance"] == 0.7
    assert parsed["context_coverage"] == 0.6


@patch("src.security.judge._get_llm")
def test_evaluer_reponse_multi_returns_overall(mock_get_llm):
    llm = Mock()
    llm.invoke.return_value = Mock(content='{"context_relevance":0.8,"faithfulness":0.7,"answer_relevance":0.9,"context_coverage":0.6}')
    mock_get_llm.return_value = llm

    scores = evaluer_reponse_multi("Question ?", "Reponse")

    assert scores is not None
    assert scores["overall"] == 0.75


@patch("src.security.judge.evaluer_reponse_multi", return_value=None)
@patch("src.security.judge._get_llm")
def test_evaluer_reponse_fallback_numeric_score(mock_get_llm, _mock_multi):
    llm = Mock()
    llm.invoke.return_value = Mock(content="0.73")
    mock_get_llm.return_value = llm

    score = evaluer_reponse("Question ?", "Reponse")
    assert score == 0.73
