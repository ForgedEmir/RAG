"""
Tests unitaires pour le module search (version LangChain + Qdrant)
Teste la fonction rechercher_passages et le router adaptatif.
"""
from unittest.mock import Mock, patch
from langchain_core.documents import Document

from src.search.search import rechercher_passages, _route


# ===== TESTS DU ROUTER ADAPTATIF =====

def test_router_question_simple_courte():
    """Une question courte (< 6 mots) sans signal complexe → mode simple."""
    plan = _route("Qui est Elarion ?")
    assert plan.use_expansion is False
    assert plan.use_reranker  is False
    assert plan.k_candidates  == 5


def test_router_question_longue_complexe():
    """Une question longue (≥ 6 mots) → mode complexe."""
    plan = _route("Quels sont les pouvoirs magiques des elfes anciens ?")
    assert plan.use_reranker  is False
    assert plan.k_candidates  == 10


def test_router_mot_cle_complexe_declenche_mode_complexe():
    """Un mot-clé signal (comment, pourquoi, différence…) → mode complexe même si court."""
    for question in [
        "comment fonctionne la magie",
        "pourquoi Elarion est parti",
        "différence entre les factions",
        "compare les deux royaumes",
    ]:
        plan = _route(question)
        assert plan.use_reranker is False, f"Le reranker est désactivé par défaut : '{question}'"
        assert plan.k_candidates == 10


def test_router_expansion_desactivee_par_defaut():
    """Query expansion désactivée par défaut même sur requête complexe."""
    plan = _route("Comment fonctionne le système de magie dans Aethelgard ?")
    assert plan.use_expansion is False   # QUERY_EXPANSION_ENABLED=false par défaut
    assert plan.use_reranker  is False   # reranker désactivé par défaut


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
def test_resultats_multiples(mock_search, mock_get_store):
    """On peut chercher et trouver plusieurs passages de plusieurs sources."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage 1", metadata={"fichier": "doc1.md"}),
        Document(page_content="Passage 2", metadata={"fichier": "doc2.md"}),
        Document(page_content="Passage 3", metadata={"fichier": "doc1.md"})
    ]

    passages, sources = rechercher_passages("Qui est le heros?")

    assert len(passages) == 3
    assert passages[0] == "Passage 1"
    assert passages[1] == "Passage 2"
    assert passages[2] == "Passage 3"
    # 2 sources uniques (doc1.md et doc2.md, pas de doublon)
    assert len(sources) == 2
    assert "doc1.md" in sources
    assert "doc2.md" in sources


@patch('src.search.search.get_store')
@patch('src.search.search.search')
def test_sans_resultats(mock_search, mock_get_store):
    """Quand il n'y a aucun resultat, on recoit des listes vides."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = []

    passages, sources = rechercher_passages("Question introuvable")

    assert len(passages) == 0
    assert len(sources) == 0


@patch('src.search.search.get_store')
@patch('src.search.search.search')
def test_un_resultat(mock_search, mock_get_store):
    """On peut trouver un seul passage d'une seule source."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Unique passage", metadata={"fichier": "unique.md"})
    ]

    passages, sources = rechercher_passages("Question simple")

    assert len(passages) == 1
    assert passages[0] == "Unique passage"
    assert len(sources) == 1
    assert sources[0] == "unique.md"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
def test_dedoublonne_sources(mock_search, mock_get_store):
    """Les sources en double ne sont gardees qu'une seule fois."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage 1", metadata={"fichier": "doc1.md"}),
        Document(page_content="Passage 2", metadata={"fichier": "doc1.md"}),
        Document(page_content="Passage 3", metadata={"fichier": "doc2.md"})
    ]

    passages, sources = rechercher_passages("Question")

    assert len(passages) == 3
    # 2 sources uniques, pas 3
    assert len(sources) == 2
    assert sources[0] == "doc1.md"
    assert sources[1] == "doc2.md"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
def test_ordre_sources_preserve(mock_search, mock_get_store):
    """L'ordre des sources suit l'ordre d'apparition des passages."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="P1", metadata={"fichier": "doc1.md"}),
        Document(page_content="P2", metadata={"fichier": "doc2.md"}),
        Document(page_content="P3", metadata={"fichier": "doc3.md"})
    ]

    passages, sources = rechercher_passages("Question")

    assert sources[0] == "doc1.md"
    assert sources[1] == "doc2.md"
    assert sources[2] == "doc3.md"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
def test_metadonnees_manquantes(mock_search, mock_get_store):
    """Si le nom de fichier est manquant, on met 'inconnu'."""
    mock_get_store.return_value = Mock()
    mock_search.return_value = [
        Document(page_content="Passage sans source", metadata={})
    ]

    passages, sources = rechercher_passages("Question")

    assert len(passages) == 1
    assert len(sources) == 1
    assert sources[0] == "inconnu"


@patch('src.search.search.get_store')
@patch('src.search.search.search')
def test_parametres_search(mock_search, mock_get_store):
    """La fonction appelle search avec les bons parametres."""
    mock_store = Mock()
    mock_get_store.return_value = mock_store
    mock_search.return_value = []

    question = "Ma question de test"
    rechercher_passages(question)

    # On verifie que search a ete appele avec le bon store, question et k=5
    mock_search.assert_called_once_with(mock_store, question, k=5)
