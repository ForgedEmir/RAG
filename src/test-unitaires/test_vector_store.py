"""
Tests unitaires pour le module vector_store (Qdrant via LangChain)

Ce fichier teste les fonctions d'ajout, recherche et suppression dans Qdrant.
On utilise des mocks pour simuler Qdrant sans vraiment l'utiliser.
"""
from unittest.mock import Mock, MagicMock, patch
from langchain_core.documents import Document


# ===== TESTS POUR add_documents =====

@patch('src.ingestion.vector_store._get_embeddings')
def test_ajouter_documents(mock_embeddings):
    """On peut ajouter des Documents LangChain dans le store."""
    from src.ingestion.vector_store import add_documents

    mock_store = Mock()
    documents = [
        Document(page_content="Premier morceau", metadata={"fichier": "test.md"}),
        Document(page_content="Deuxieme morceau", metadata={"fichier": "test.md"})
    ]

    add_documents(mock_store, documents)

    mock_store.add_documents.assert_called_once_with(documents)


@patch('src.ingestion.vector_store._get_embeddings')
def test_ajouter_documents_vides(mock_embeddings):
    """Avec une liste vide, rien ne se passe."""
    from src.ingestion.vector_store import add_documents

    mock_store = Mock()
    add_documents(mock_store, [])

    mock_store.add_documents.assert_not_called()


# ===== TESTS POUR remove_files =====

@patch('src.ingestion.vector_store._get_embeddings')
def test_supprimer_fichiers(mock_embeddings):
    """On peut supprimer les documents d'un fichier specifique."""
    from src.ingestion.vector_store import remove_files

    mock_store = Mock()
    mock_store.client = Mock()

    remove_files(mock_store, {"test.md"})

    # Le client Qdrant doit etre appele avec delete()
    mock_store.client.delete.assert_called_once()


@patch('src.ingestion.vector_store._get_embeddings')
def test_supprimer_fichiers_vides(mock_embeddings):
    """Avec un set vide, rien ne se passe."""
    from src.ingestion.vector_store import remove_files

    mock_store = Mock()
    mock_store.client = Mock()

    remove_files(mock_store, set())

    mock_store.client.delete.assert_not_called()


@patch('src.ingestion.vector_store._get_embeddings')
def test_supprimer_plusieurs_fichiers(mock_embeddings):
    """On peut supprimer les documents de plusieurs fichiers."""
    from src.ingestion.vector_store import remove_files

    mock_store = Mock()
    mock_store.client = Mock()

    remove_files(mock_store, {"file1.md", "file2.md"})

    # delete() doit etre appele une seule fois (batch)
    assert mock_store.client.delete.call_count == 1


# ===== TESTS POUR search =====

@patch('src.ingestion.vector_store._get_embeddings')
def test_recherche(mock_embeddings):
    """On peut rechercher des documents similaires."""
    from src.ingestion.vector_store import search

    mock_store = Mock()
    mock_store.similarity_search.return_value = [
        Document(page_content="Resultat 1", metadata={"fichier": "doc1.md"}),
        Document(page_content="Resultat 2", metadata={"fichier": "doc2.md"})
    ]

    results = search(mock_store, "Ma question", k=3)

    assert len(results) == 2
    assert results[0].page_content == "Resultat 1"
    mock_store.similarity_search.assert_called_once_with("Ma question", k=3)


# ===== TESTS POUR get_store =====

@patch('src.ingestion.vector_store.QdrantClient')
@patch('src.ingestion.vector_store._get_embeddings')
@patch('src.ingestion.vector_store.QdrantVectorStore')
def test_get_store_cree_collection(mock_qdrant_vs, mock_embeddings, mock_client_class):
    """get_store cree la collection si elle n'existe pas."""
    from src.ingestion.vector_store import get_store

    mock_client = Mock()
    mock_client_class.return_value = mock_client
    # Simuler qu'aucune collection n'existe
    mock_client.get_collections.return_value = Mock(collections=[])

    get_store(force_reindex=False)

    # La collection doit etre creee
    mock_client.create_collection.assert_called_once()


@patch('src.ingestion.vector_store.os.path.exists')
@patch('src.ingestion.vector_store.QdrantClient')
@patch('src.ingestion.vector_store._get_embeddings')
@patch('src.ingestion.vector_store.QdrantVectorStore')
def test_get_store_force_reindex(mock_qdrant_vs, mock_embeddings, mock_client_class, mock_path_exists):
    """Avec force_reindex, le dossier qdrant_db est supprime puis recree."""
    from src.ingestion.vector_store import get_store

    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_collections.return_value = Mock(collections=[])
    mock_path_exists.return_value = True

    with patch('shutil.rmtree') as mock_rmtree:
        get_store(force_reindex=True)

        # Le dossier qdrant_db doit etre supprime
        mock_rmtree.assert_called_once()
