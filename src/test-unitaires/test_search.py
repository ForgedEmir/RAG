"""
Tests unitaires pour le module search
Teste la fonction rechercher_passages qui recherche dans ChromaDB.
"""

from unittest.mock import Mock, MagicMock, patch
import sys

# Note importante pour les débutants :
# On simule (mock) ChromaDB et fastembed pour ne pas télécharger de vrais modèles.
# Ça rend les tests rapides et prévisibles.
sys.modules['fastembed'] = MagicMock()
sys.modules['fastembed.TextEmbedding'] = MagicMock()

from src.search.search import rechercher_passages


# ===== TESTS POUR rechercher_passages =====

@patch('src.search.search._get_collection')
def test_resultats_multiples(mock_get_collection):
    """On peut chercher et trouver plusieurs passages de plusieurs sources."""
    # On simule une collection ChromaDB
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [["Passage 1", "Passage 2", "Passage 3"]],
        "metadatas": [[
            {"fichier": "doc1.md"},
            {"fichier": "doc2.md"},
            {"fichier": "doc1.md"}
        ]]
    }
    mock_get_collection.return_value = fausse_collection
    
    # On recherche
    passages, sources = rechercher_passages("Qui est le héros?")
    
    # On vérifie qu'on a bien les 3 passages
    assert len(passages) == 3
    assert passages[0] == "Passage 1"
    assert passages[1] == "Passage 2"
    assert passages[2] == "Passage 3"
    # On a 2 sources uniques (doc1.md et doc2.md, pas de doublon)
    assert len(sources) == 2
    assert "doc1.md" in sources
    assert "doc2.md" in sources


@patch('src.search.search._get_collection')
def test_sans_resultats(mock_get_collection):
    """Quand il n'y a aucun résultat, on reçoit des listes vides."""
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]]
    }
    mock_get_collection.return_value = fausse_collection
    
    passages, sources = rechercher_passages("Question introuvable")
    
    assert len(passages) == 0
    assert len(sources) == 0


@patch('src.search.search._get_collection')
def test_un_resultat(mock_get_collection):
    """On peut trouver un seul passage d'une seule source."""
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [["Unique passage"]],
        "metadatas": [[{"fichier": "unique.md"}]]
    }
    mock_get_collection.return_value = fausse_collection
    
    passages, sources = rechercher_passages("Question simple")
    
    assert len(passages) == 1
    assert passages[0] == "Unique passage"
    assert len(sources) == 1
    assert sources[0] == "unique.md"


@patch('src.search.search._get_collection')
def test_dedoublonne_sources(mock_get_collection):
    """Les sources en double ne sont gardées qu'une seule fois."""
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [["Passage 1", "Passage 2", "Passage 3"]],
        "metadatas": [[
            {"fichier": "doc1.md"},
            {"fichier": "doc1.md"},  # Doublon
            {"fichier": "doc2.md"}
        ]]
    }
    mock_get_collection.return_value = fausse_collection
    
    passages, sources = rechercher_passages("Question")
    
    assert len(passages) == 3
    # 2 sources uniques, pas 3
    assert len(sources) == 2
    assert sources[0] == "doc1.md"
    assert sources[1] == "doc2.md"


@patch('src.search.search._get_collection')
def test_ordre_sources_preserve(mock_get_collection):
    """L'ordre des sources suit l'ordre d'apparition des passages."""
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [["P1", "P2", "P3"]],
        "metadatas": [[
            {"fichier": "doc1.md"},
            {"fichier": "doc2.md"},
            {"fichier": "doc3.md"}
        ]]
    }
    mock_get_collection.return_value = fausse_collection
    
    passages, sources = rechercher_passages("Question")
    
    assert sources[0] == "doc1.md"
    assert sources[1] == "doc2.md"
    assert sources[2] == "doc3.md"


@patch('src.search.search._get_collection')
def test_metadonnees_manquantes(mock_get_collection):
    """Si le nom de fichier est manquant, on met "inconnu"."""
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [["Passage sans source"]],
        "metadatas": [[{}]]  # Pas de clé "fichier"
    }
    mock_get_collection.return_value = fausse_collection
    
    passages, sources = rechercher_passages("Question")
    
    assert len(passages) == 1
    assert len(sources) == 1
    assert sources[0] == "inconnu"


@patch('src.search.search._get_collection')
def test_parametres_query(mock_get_collection):
    """La fonction appelle query avec les bons paramètres."""
    fausse_collection = Mock()
    fausse_collection.query.return_value = {
        "documents": [[]],
        "metadatas": [[]]
    }
    mock_get_collection.return_value = fausse_collection
    question = "Ma question de test"
    
    rechercher_passages(question)
    
    # On vérifie que query a été appelé une fois
    fausse_collection.query.assert_called_once()
    # On vérifie les paramètres
    parametres = fausse_collection.query.call_args.kwargs
    assert parametres["query_texts"] == [question]
    assert parametres["n_results"] == 3
