"""
Unit tests for the vector_store module (Qdrant via LangChain)

This file tests the add, search, and delete functions in Qdrant.
We use mocks to simulate Qdrant without actually using it.
"""
from unittest.mock import Mock, patch
import pytest
from langchain_core.documents import Document


# ===== TESTS FOR add_documents =====

@patch('src.ingestion.vector_store._get_embeddings')
def test_ajouter_documents(mock_embeddings):
    """We can add LangChain Documents to the store."""
    from src.ingestion.vector_store import add_documents

    mock_store = Mock()
    documents = [
        Document(page_content="First chunk", metadata={"filename": "test.md"}),
        Document(page_content="Second chunk", metadata={"filename": "test.md"})
    ]

    add_documents(mock_store, documents)

    mock_store.add_documents.assert_called_once_with(documents)


@patch('src.ingestion.vector_store._get_embeddings')
def test_ajouter_documents_vides(mock_embeddings):
    """With an empty list, nothing happens."""
    from src.ingestion.vector_store import add_documents

    mock_store = Mock()
    add_documents(mock_store, [])

    mock_store.add_documents.assert_not_called()


# ===== TESTS FOR remove_files =====

@patch('src.ingestion.vector_store._get_embeddings')
def test_supprimer_fichiers(mock_embeddings):
    """We can delete documents for a specific file."""
    from src.ingestion.vector_store import remove_files

    mock_store = Mock()
    mock_store.client = Mock()

    remove_files(mock_store, {"test.md"})

    # The Qdrant client must be called with delete()
    mock_store.client.delete.assert_called_once()


@patch('src.ingestion.vector_store._get_embeddings')
def test_supprimer_fichiers_vides(mock_embeddings):
    """With an empty set, nothing happens."""
    from src.ingestion.vector_store import remove_files

    mock_store = Mock()
    mock_store.client = Mock()

    remove_files(mock_store, set())

    mock_store.client.delete.assert_not_called()


@patch('src.ingestion.vector_store._get_embeddings')
def test_supprimer_plusieurs_fichiers(mock_embeddings):
    """We can delete documents for multiple files."""
    from src.ingestion.vector_store import remove_files

    mock_store = Mock()
    mock_store.client = Mock()

    remove_files(mock_store, {"file1.md", "file2.md"})

    # delete() must be called only once (batch)
    assert mock_store.client.delete.call_count == 1


# ===== TESTS FOR search =====

@patch('src.ingestion.vector_store._get_embeddings')
def test_recherche(mock_embeddings):
    """We can search for similar documents."""
    from src.ingestion.vector_store import search

    mock_store = Mock()
    mock_store.similarity_search.return_value = [
        Document(page_content="Result 1", metadata={"filename": "doc1.md"}),
        Document(page_content="Result 2", metadata={"filename": "doc2.md"})
    ]

    results = search(mock_store, "My question", k=3)

    assert len(results) == 2
    assert results[0].page_content == "Result 1"
    mock_store.similarity_search.assert_called_once_with("My question", k=3)


# ===== TESTS FOR get_store =====

@patch('src.ingestion.vector_store.QdrantClient')
@patch('src.ingestion.vector_store._get_embeddings')
@patch('src.ingestion.vector_store.QdrantVectorStore')
def test_get_store_cree_collection(mock_qdrant_vs, mock_embeddings, mock_client_class):
    """get_store creates the collection if it does not exist."""
    import src.ingestion.vector_store as vs
    from src.ingestion.vector_store import get_store

    # Reset singletons to isolate this test
    vs._collection_ready = False
    vs._client = None

    mock_client = Mock()
    mock_client_class.return_value = mock_client
    # Simulate that no collection exists
    mock_client.get_collections.return_value = Mock(collections=[])

    get_store(force_reindex=False)

    # The collection must be created
    mock_client.create_collection.assert_called_once()



@patch('src.ingestion.vector_store._QDRANT_URL', None)
@patch('src.ingestion.vector_store.os.path.exists')
@patch('src.ingestion.vector_store.QdrantClient')
@patch('src.ingestion.vector_store._get_embeddings')
@patch('src.ingestion.vector_store.QdrantVectorStore')
def test_get_store_force_reindex(mock_qdrant_vs, mock_embeddings, mock_client_class, mock_path_exists):
    """With force_reindex, the qdrant_db folder is deleted then recreated."""
    from src.ingestion.vector_store import get_store

    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_collections.return_value = Mock(collections=[])

    # Simulates that the folder and file exist to avoid FileNotFoundError
    def path_exists_side_effect(path):
        if path.endswith("files_metadata.json"):
            return True
        return True
    mock_path_exists.side_effect = path_exists_side_effect

    with patch('builtins.open'), patch('shutil.rmtree') as mock_rmtree:
        get_store(force_reindex=True)
        mock_rmtree.assert_called_once()


@patch('src.ingestion.vector_store.QdrantClient')
@patch('src.ingestion.vector_store._get_embeddings')
@patch('src.ingestion.vector_store.QdrantVectorStore')
def test_get_store_recree_si_dimension_mismatch(mock_qdrant_vs, mock_embeddings, mock_client_class):
    """The collection is recreated automatically if the dimension does not match."""
    import src.ingestion.vector_store as vs
    from src.ingestion.vector_store import get_store

    vs._collection_ready = False
    vs._client = None
    vs._vector_size = None

    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2, 0.3]
    mock_embeddings.return_value = embedder

    mock_client = Mock()
    mock_client_class.return_value = mock_client
    existing_collection = Mock()
    existing_collection.name = vs._COLLECTION_NAME
    mock_client.get_collections.return_value = Mock(collections=[existing_collection])

    info = Mock()
    info.config.params.vectors = Mock(size=5)
    mock_client.get_collection.return_value = info

    with patch.object(vs, "_QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH", True), \
         patch.object(vs, "_get_expected_vector_size", return_value=3):
        get_store(force_reindex=False)

    mock_client.delete_collection.assert_called_with(vs._COLLECTION_NAME)
    mock_client.create_collection.assert_called_once()


@patch('src.ingestion.vector_store.QdrantClient')
@patch('src.ingestion.vector_store._get_embeddings')
@patch('src.ingestion.vector_store.QdrantVectorStore')
def test_get_store_mismatch_no_auto_recreate_raises(mock_qdrant_vs, mock_embeddings, mock_client_class):
    """Without auto-recreate, a dimension mismatch raises an explicit error."""
    import pytest
    import src.ingestion.vector_store as vs
    from src.ingestion.vector_store import get_store

    vs._collection_ready = False
    vs._client = None
    vs._vector_size = None

    embedder = Mock()
    embedder.embed_query.return_value = [0.1, 0.2, 0.3]
    mock_embeddings.return_value = embedder

    mock_client = Mock()
    mock_client_class.return_value = mock_client
    existing_collection = Mock()
    existing_collection.name = vs._COLLECTION_NAME
    mock_client.get_collections.return_value = Mock(collections=[existing_collection])

    info = Mock()
    info.config.params.vectors = Mock(size=8)
    mock_client.get_collection.return_value = info

    with patch.object(vs, "_QDRANT_AUTO_RECREATE_ON_DIM_MISMATCH", False), \
         patch.object(vs, "_get_expected_vector_size", return_value=3):
        with pytest.raises(RuntimeError):
            get_store(force_reindex=False)


@patch('src.ingestion.vector_store.FastEmbedEmbeddings')
def test_get_embeddings_retry_apres_cache_corrompu(mock_fastembed):
    """If model.onnx_data is missing, the cache is purged and init is retried."""
    import src.ingestion.vector_store as vs

    vs._embeddings = None

    broken = RuntimeError(
        "No such file or directory [/tmp/fastembed_cache/models--qdrant--multilingual-e5-large-onnx/snapshots/abc/model.onnx_data]"
    )
    ready = Mock()
    mock_fastembed.side_effect = [broken, ready]

    with patch('src.ingestion.vector_store._purge_corrupted_fastembed_cache') as mock_purge:
        emb = vs._get_embeddings()

    assert emb is ready
    assert mock_fastembed.call_count == 2
    mock_purge.assert_called_once()


@patch('src.ingestion.vector_store.FastEmbedEmbeddings')
def test_get_embeddings_non_cache_error_no_retry(mock_fastembed):
    """A non-cache-related error must bubble up directly."""
    import src.ingestion.vector_store as vs

    vs._embeddings = None
    mock_fastembed.side_effect = RuntimeError("invalid configuration")

    with patch('src.ingestion.vector_store._purge_corrupted_fastembed_cache') as mock_purge:
        with pytest.raises(RuntimeError):
            vs._get_embeddings()

    assert mock_fastembed.call_count == 1
    mock_purge.assert_not_called()
