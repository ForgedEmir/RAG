"""Tests unitaires — Context-Aware Chunking (doc_summary + entities dans metadata)."""
import json
from unittest.mock import MagicMock, patch

import pytest


@patch("src.ingestion.run._get_redis", return_value=None)  # pas de Redis en test
@patch("src.ingestion.run._get_llm_checker")
def test_doc_context_retourne_summary_et_entities(mock_llm_factory, mock_redis):
    """_get_doc_context doit retourner un dict avec 'doc_summary' et 'entities'."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='{"summary": "Résumé test.", "entities": ["Aethon", "Vael"]}'
    )
    mock_llm_factory.return_value = mock_llm

    from src.ingestion.run import _get_doc_context
    # On crée un ChatOpenAI mock pour la summary_llm interne
    with patch("src.ingestion.run.ChatOpenAI", return_value=mock_llm):
        result = _get_doc_context("Texte de lore test sur Aethon et Vael.", "lore.md")

    assert "doc_summary" in result
    assert "entities" in result
    assert isinstance(result["entities"], list)


@patch("src.ingestion.run._is_lore_content", return_value=True)
@patch("src.ingestion.run._get_doc_context")
@patch("src.ingestion.run.extract_text_from_file", return_value="Texte de lore test.")
@patch("src.ingestion.run.os.path.exists", return_value=True)
def test_chunks_ont_metadata_enrichie(mock_exists, mock_extract, mock_context, mock_lore):
    """Chaque chunk produit par prepare_files_for_ai doit avoir doc_summary et entities."""
    mock_context.return_value = {"doc_summary": "Un résumé.", "entities": ["Entité1"]}

    import src.ingestion.run as run_module
    from src.ingestion.run import prepare_files_for_ai
    # Force custom parser mode pour éviter l'import de unstructured (crash libmagic Windows)
    original_parser = run_module.PARSER_MODE
    run_module.PARSER_MODE = "custom"
    try:
        docs = prepare_files_for_ai({"test.md"})
    finally:
        run_module.PARSER_MODE = original_parser

    assert len(docs) > 0
    for doc in docs:
        assert "doc_summary" in doc.metadata
        assert "entities" in doc.metadata
        assert doc.metadata["doc_summary"] == "Un résumé."


@patch("src.ingestion.run._get_redis")
@patch("src.ingestion.run.ChatOpenAI")
def test_cache_redis_utilise_si_disponible(mock_llm_cls, mock_redis_factory):
    """_get_doc_context doit utiliser le cache Redis si disponible."""
    cached_data = {"doc_summary": "Depuis cache Redis.", "entities": ["CacheEntité"]}
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(cached_data)
    mock_redis_factory.return_value = mock_redis

    from src.ingestion.run import _get_doc_context
    result = _get_doc_context("Texte quelconque.", "test.md")

    assert result["doc_summary"] == "Depuis cache Redis."
    mock_llm_cls.assert_not_called()   # LLM pas appelé si cache hit
