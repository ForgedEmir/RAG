"""
Tests unitaires pour le module search (version LangChain + Qdrant)
Teste la fonction rechercher_passages et le router adaptatif.
"""
from unittest.mock import Mock, patch, MagicMock
from langchain_core.documents import Document

from src.search.search import (
    rechercher_passages,
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
    """Un mot-clé signal (comment, pourquoi, différence…) → mode complexe même si court."""
    for question in [
        "comment fonctionne la magie",
        "pourquoi Elarion est parti",
        "différence entre les factions",
        "compare les deux royaumes",
    ]:
        plan = _route(question)
        assert plan.k_candidates == CANDIDATES_COMPLEX


def test_router_expansion_desactivee_par_defaut():
    """Query expansion désactivée par défaut même sur requête complexe."""
    plan = _route("Comment fonctionne le système de magie dans Aethelgard ?")
    assert plan.use_expansion is False   # QUERY_EXPANSION_ENABLED=false par défaut


def test_router_reranker_actif_par_defaut():
    """RERANKER_ENABLED=true par défaut → reranker actif."""
    with patch("src.search.search._RERANKER_ENABLED", True):
        plan = _route("Qui est Elarion ?")
        assert plan.use_reranker is True


def test_router_expansion_activee_si_flag():
    """Query expansion activée si QUERY_EXPANSION_ENABLED=true ET question complexe."""
    with patch("src.search.search._QUERY_EXPANSION_ENABLED", True):
        plan = _route("Comment fonctionne le système de magie dans Aethelgard ?")
        assert plan.use_expansion is True

    # Mais toujours désactivée pour une question simple
    with patch("src.search.search._QUERY_EXPANSION_ENABLED", True):
        plan = _route("Qui est Elarion ?")
        assert plan.use_expansion is False


def test_router_reranker_activable_si_flag():
    """RERANKER_ENABLED=true réactive le reranker sur requête complexe."""
    with patch("src.search.search._RERANKER_ENABLED", True):
        plan = _route("Comment fonctionne la magie dans ce monde ?")
        assert plan.use_reranker is True


# ===== TESTS POUR rechercher_passages =====

@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)  # désactive HyDE fallback
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_resultats_multiples(mock_search, mock_get_store):
    """On peut chercher et trouver plusieurs passages de plusieurs sources."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage 1", metadata={"fichier": "doc1.md", "chunk_id": "doc1_0"}),
        Document(page_content="Passage 2", metadata={"fichier": "doc2.md", "chunk_id": "doc2_0"}),
        Document(page_content="Passage 3", metadata={"fichier": "doc3.md", "chunk_id": "doc3_0"})
    ]

    passages, sources, _ = rechercher_passages("Qui est le heros uniquement?")

    assert len(passages) == 3
    assert passages[0] == "Passage 1"
    assert "doc1.md" in sources
    assert "doc2.md" in sources
    assert "doc3.md" in sources


@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_sans_resultats(mock_search, mock_get_store):
    """Quand il n'y a aucun résultat, on reçoit des listes vides."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = []

    passages, sources, _ = rechercher_passages("Question introuvable zzzxxx999")

    assert len(passages) == 0
    assert len(sources) == 0


@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_un_resultat(mock_search, mock_get_store):
    """On peut trouver un seul passage d'une seule source."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Unique passage", metadata={"fichier": "unique.md", "chunk_id": "unique_0"})
    ]

    passages, sources, _ = rechercher_passages("Question simple unique seul")

    assert len(passages) == 1
    assert passages[0] == "Unique passage"
    assert len(sources) == 1
    assert sources[0] == "unique.md"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_dedoublonne_par_fichier(mock_search, mock_get_store):
    """La deduplication par fichier ne garde que le meilleur passage par source."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage 1", metadata={"fichier": "doc1.md", "chunk_id": "doc1_0"}),
        Document(page_content="Passage 2", metadata={"fichier": "doc1.md", "chunk_id": "doc1_1"}),
        Document(page_content="Passage 3", metadata={"fichier": "doc2.md", "chunk_id": "doc2_0"})
    ]

    passages, sources, _ = rechercher_passages("Question dedoublonnage")

    # Après deduplication : 1 passage par fichier → 2 fichiers = 2 passages
    assert len(passages) == 2
    assert "doc1.md" in sources
    assert "doc2.md" in sources


@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_ordre_sources_preserve(mock_search, mock_get_store):
    """L'ordre des sources suit les scores RRF (décroissant)."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="P1", metadata={"fichier": "doc1.md", "chunk_id": "doc1_0"}),
        Document(page_content="P2", metadata={"fichier": "doc2.md", "chunk_id": "doc2_0"}),
        Document(page_content="P3", metadata={"fichier": "doc3.md", "chunk_id": "doc3_0"})
    ]

    passages, sources, _ = rechercher_passages("Question ordre sources")

    assert sources[0] == "doc1.md"
    assert sources[1] == "doc2.md"
    assert sources[2] == "doc3.md"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_metadonnees_manquantes(mock_search, mock_get_store):
    """Si le nom de fichier est manquant, on met 'inconnu'."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage sans source", metadata={})
    ]

    passages, sources, _ = rechercher_passages("Question metadonnees manquantes")

    assert len(passages) == 1
    assert len(sources) == 1
    assert sources[0] == "inconnu"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
@patch('src.search.search._RERANKER_ENABLED', False)
@patch('src.search.search._HYDE_THRESHOLD', -1.0)
@patch('src.search.search._bm25_index', None)
@patch('src.search.search._bm25_corpus', [])
@patch('src.search.search._bm25_loaded', True)
def test_parametres_search(mock_search, mock_get_store):
    """La fonction appelle search avec les bons paramètres."""
    mock_store = Mock()
    mock_get_store.return_value = mock_store
    mock_search.return_value = []

    question = "Ma question de test"
    rechercher_passages(question)

    mock_search.assert_called_once_with(mock_store, question, k=CANDIDATES_SIMPLE)


def test_runtime_switches_snapshot_contains_expected_keys():
    """Le snapshot runtime expose les switches lisibles par le monitoring."""
    sw = get_runtime_switches()
    assert "reranker_enabled" in sw
    assert "query_expansion_enabled" in sw
    assert "smart_rerank_enabled" in sw
    assert "reranker_model" in sw


def test_bm25_tokenizer_normalise_accents_et_stopwords_fr():
    tokens = _tokenize_bm25("L'épée de l'Oracle et des héros est dans la cité.")
    assert "epee" in tokens
    assert "oracle" in tokens
    assert "heros" in tokens
    assert "de" not in tokens
    assert "et" not in tokens
