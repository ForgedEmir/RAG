"""
Tests unitaires pour le module search (version LangChain + Qdrant)
Teste la fonction search_passages et le router adaptatif.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.documents import Document

from src.search.search import (
    search_passages,
    _route,
    _tokenize_bm25,
    CANDIDATES_SIMPLE,
    CANDIDATES_COMPLEX,
    get_runtime_switches,
)


# ===== TESTS DU ROUTER ADAPTATIF =====

def test_router_question_simple_courte():
    """Une question courte (< 6 mots) sans signal complexe → k_candidates=5."""
    plan = _route("Qui est Elarion ?")
    assert plan.use_expansion is False
    assert plan.k_candidates == CANDIDATES_SIMPLE


def test_router_question_longue_complexe():
    """Une question longue (≥ 6 mots) → mode complexe k=100."""
    plan = _route("Quels sont les pouvoirs magiques des elfes anciens ?")
    assert plan.k_candidates == CANDIDATES_COMPLEX


def test_router_mot_cle_complexe_declenche_mode_complexe():
    """A signal keyword (how, why, difference...) -> complex mode even if short."""
    for question in [
        "how does magic work",
        "why did Elarion leave",
        "difference between factions",
        "compare the two kingdoms",
    ]:
        plan = _route(question)
        assert plan.k_candidates == CANDIDATES_COMPLEX


def test_router_expansion_desactivee_par_defaut():
    """Query expansion disabled by default even on complex query."""
    plan = _route("How does the magic system work in Aethelgard?")
    assert plan.use_expansion is False   # QUERY_EXPANSION_ENABLED=false by default


def test_router_reranker_actif_par_defaut():
    """RERANKER_ENABLED=true by default -> reranker active."""
    with patch("src.search.search._RERANKER_ENABLED", True):
        plan = _route("Qui est Elarion ?")
        assert plan.use_reranker is True


def test_router_expansion_activee_si_flag():
    """Query expansion active if QUERY_EXPANSION_ENABLED=true AND complex question."""
    with patch("src.search.search._QUERY_EXPANSION_ENABLED", True):
        plan = _route("How does the magic system work in Aethelgard?")
        assert plan.use_expansion is True

    # But always disabled for a simple question
    with patch("src.search.search._QUERY_EXPANSION_ENABLED", True):
        plan = _route("Qui est Elarion ?")
        assert plan.use_expansion is False


def test_router_reranker_activable_si_flag():
    """RERANKER_ENABLED=true reactivates reranker on complex query."""
    with patch("src.search.search._RERANKER_ENABLED", True):
        plan = _route("Comment fonctionne la magie dans ce monde ?")
        assert plan.use_reranker is True


# ===== TESTS POUR search_passages =====

@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)  # disables HyDE fallback
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_resultats_multiples(mock_search, mock_get_store):
    """On peut chercher et trouver plusieurs passages de plusieurs sources."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage 1", metadata={"filename": "doc1.md", "chunk_id": "doc1_0"}),
        Document(page_content="Passage 2", metadata={"filename": "doc2.md", "chunk_id": "doc2_0"}),
        Document(page_content="Passage 3", metadata={"filename": "doc3.md", "chunk_id": "doc3_0"})
    ]

    passages, sources, *_ = await search_passages("Qui est le heros uniquement?")

    assert len(passages) == 3
    assert passages[0] == "Passage 1"
    assert "doc1.md" in sources
    assert "doc2.md" in sources
    assert "doc3.md" in sources


@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_sans_resultats(mock_search, mock_get_store):
    """When there are no results, empty lists are returned."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = []

    passages, sources, *_ = await search_passages("Question introuvable zzzxxx999")

    assert len(passages) == 0
    assert len(sources) == 0


@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_un_resultat(mock_search, mock_get_store):
    """On peut trouver un seul passage d'une seule source."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Unique passage", metadata={"filename": "unique.md", "chunk_id": "unique_0"})
    ]

    passages, sources, *_ = await search_passages("Question simple unique seul")

    assert len(passages) == 1
    assert passages[0] == "Unique passage"
    assert len(sources) == 1
    assert sources[0] == "unique.md"


@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_dedoublonne_par_fichier(mock_search, mock_get_store):
    """La deduplication par fichier ne garde que le meilleur passage par source."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage 1", metadata={"filename": "doc1.md", "chunk_id": "doc1_0"}),
        Document(page_content="Passage 2", metadata={"filename": "doc1.md", "chunk_id": "doc1_1"}),
        Document(page_content="Passage 3", metadata={"filename": "doc2.md", "chunk_id": "doc2_0"})
    ]

    passages, sources, *_ = await search_passages("Question dedoublonnage")

    # After deduplication: 1 passage per file -> 2 files = 2 passages
    assert len(passages) == 2
    assert "doc1.md" in sources
    assert "doc2.md" in sources


@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_ordre_sources_preserve(mock_search, mock_get_store):
    """Source order follows RRF scores (descending)."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="P1", metadata={"filename": "doc1.md", "chunk_id": "doc1_0"}),
        Document(page_content="P2", metadata={"filename": "doc2.md", "chunk_id": "doc2_0"}),
        Document(page_content="P3", metadata={"filename": "doc3.md", "chunk_id": "doc3_0"})
    ]

    passages, sources, *_ = await search_passages("Question ordre sources")

    assert sources[0] == "doc1.md"
    assert sources[1] == "doc2.md"
    assert sources[2] == "doc3.md"


@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_metadonnees_manquantes(mock_search, mock_get_store):
    """Si le nom de fichier est manquant, on met 'inconnu'."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage sans source", metadata={})
    ]

    passages, sources, *_ = await search_passages("Question metadonnees manquantes")

    assert len(passages) == 1
    assert len(sources) == 1
    assert sources[0] == "unknown"


@pytest.mark.asyncio
@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._get_bm25_for_tenant', new=lambda *a, **kw: (None, []))
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
async def test_parametres_search(mock_search, mock_get_store):
    """The function calls search with the correct parameters."""
    mock_store = Mock()
    mock_get_store.return_value = mock_store
    mock_search.return_value = []

    question = "Ma question de test"
    await search_passages(question)

    mock_search.assert_called_once_with(mock_store, question, k=CANDIDATES_SIMPLE, tenant_id="")


def test_runtime_switches_snapshot_contains_expected_keys():
    """Le snapshot runtime expose les switches lisibles par le monitoring."""
    sw = get_runtime_switches()
    assert "reranker_enabled" in sw
    assert "query_expansion_enabled" in sw
    assert "smart_rerank_enabled" in sw
    assert "reranker_model" in sw


def test_bm25_tokenizer_normalises_accents_and_stopwords():
    # Uses a French sentence because the BM25 tokenizer targets French-language queries.
    # Accent normalization: épée→epee, héros→heros. French stopwords: de, et, les removed.
    tokens = _tokenize_bm25("L'épée de l'Oracle et les héros est dans la ville.")
    assert "epee" in tokens
    assert "oracle" in tokens
    assert "heros" in tokens or "hero" in tokens
    assert "de" not in tokens
    assert "les" not in tokens
