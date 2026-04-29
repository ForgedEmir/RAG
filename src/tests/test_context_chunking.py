"""Unit tests — Context-Aware Chunking (doc_summary + entities in metadata)."""
import json
from unittest.mock import MagicMock, patch



@patch("src.ingestion.run._get_redis", return_value=None)  # no Redis in test
@patch("src.ingestion.run._get_llm_checker")
def test_doc_context_retourne_summary_et_entities(mock_llm_factory, mock_redis):
    """_get_doc_context must return a dict with 'doc_summary' and 'entities'."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='{"summary": "Test summary.", "entities": ["Aethon", "Vael"]}'
    )
    mock_llm_factory.return_value = mock_llm

    from src.ingestion.run import _get_doc_context
    # We create a mock ChatOpenAI for the internal summary_llm
    with patch("src.ingestion.run.ChatOpenAI", return_value=mock_llm):
        result = _get_doc_context("Test lore text about Aethon and Vael.", "lore.md")

    assert "doc_summary" in result
    assert "entities" in result
    assert isinstance(result["entities"], list)


@patch("src.ingestion.run._is_lore_content", return_value=True)
@patch("src.ingestion.run._get_doc_context")
@patch("src.ingestion.run.extract_text_from_file", return_value="Test lore text.")
@patch("src.ingestion.run.os.path.exists", return_value=True)
def test_chunks_ont_metadata_enrichie(mock_exists, mock_extract, mock_context, mock_lore):
    """Each chunk produced by prepare_files_for_ai must have doc_summary and entities."""
    mock_context.return_value = {"doc_summary": "A summary.", "entities": ["Entity1"]}

    import src.ingestion.run as run_module
    from src.ingestion.run import prepare_files_for_ai
    # Force custom parser mode to avoid unstructured import (libmagic crash on Windows)
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
        assert doc.metadata["doc_summary"] == "A summary."


@patch("src.ingestion.run._get_redis")
@patch("src.ingestion.run.ChatOpenAI")
def test_cache_redis_utilise_si_disponible(mock_llm_cls, mock_redis_factory):
    """_get_doc_context must use the Redis cache if available."""
    cached_data = {"doc_summary": "From Redis cache.", "entities": ["CacheEntity"]}
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps(cached_data)
    mock_redis_factory.return_value = mock_redis

    from src.ingestion.run import _get_doc_context
    result = _get_doc_context("Some text.", "test.md")

    assert result["doc_summary"] == "From Redis cache."
    mock_llm_cls.assert_not_called()   # LLM not called if cache hit
