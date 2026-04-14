"""
Tests unitaires pour le module run (orchestration de l'ingestion)
Teste les fonctions load_memory, save_memory, list_current_files, prepare_files_for_ai, et index_data.
Version LangChain + Qdrant.
"""
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from langchain_core.documents import Document

from src.ingestion.run import (
    load_memory,
    save_memory,
    list_current_files,
    prepare_files_for_ai,
    index_data,
    MEMORY_FILE,
    DATA_FOLDER
)


# ===== TESTS POUR load_memory =====

@patch('os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='{"file.md": 1234567890, "doc.txt": 9876543210}')
def test_load_memory_existe(mock_file, mock_exists):
    """On peut charger la memoire depuis le fichier JSON."""
    mock_exists.return_value = True

    memory = load_memory()

    assert memory == {"file.md": 1234567890, "doc.txt": 9876543210}
    mock_exists.assert_called_once_with(MEMORY_FILE)
    mock_file.assert_called_once_with(MEMORY_FILE, 'r', encoding='utf-8')


# ===== TESTS POUR save_memory =====

def test_save_memory(tmp_path, monkeypatch):
    """save_memory écrit le JSON de manière atomique via un fichier temporaire."""
    import src.ingestion.run as run_module
    target = tmp_path / "files_metadata.json"
    monkeypatch.setattr(run_module, "MEMORY_FILE", str(target))

    fichiers = {"histoire.md": 1111111111, "personnages.txt": 2222222222}
    save_memory(fichiers)

    assert target.exists()
    import json as _json
    data = _json.loads(target.read_text(encoding="utf-8"))
    assert data == fichiers


# ===== TESTS POUR list_current_files =====

@patch('os.path.exists')
@patch('os.listdir')
@patch('os.path.getmtime')
def test_list_current_files_ok(mock_getmtime, mock_listdir, mock_exists):
    """On peut lister les fichiers supportes avec leur date de modification."""
    mock_exists.return_value = True
    mock_listdir.return_value = ["file1.md", "file2.txt", "image.png", "DOC.MD"]
    mock_getmtime.side_effect = [1000, 2000, 3000, 4000]

    fichiers = list_current_files()

    assert len(fichiers) == 3
    assert "file1.md" in fichiers
    assert "file2.txt" in fichiers
    assert "DOC.MD" in fichiers
    assert "image.png" not in fichiers


# ===== TESTS POUR prepare_files_for_ai =====

@patch('src.ingestion.run.PARSER_MODE', 'custom')
@patch('os.path.exists')
@patch('src.ingestion.run.extract_text_from_file')
@patch('src.ingestion.run.clean_text')
@patch('src.ingestion.run.split_into_chunks')
def test_prepare_files_ok(mock_split, mock_clean, mock_extract, mock_exists):
    """On peut preparer des fichiers: extraction, nettoyage, decoupage."""
    mock_exists.return_value = True
    mock_extract.return_value = "Texte brut du fichier"
    mock_clean.return_value = "Texte nettoye"
    mock_split.return_value = ["Chunk 1", "Chunk 2"]

    documents = prepare_files_for_ai({"file.md"})

    assert len(documents) == 2
    assert isinstance(documents[0], Document)
    assert documents[0].page_content == "Chunk 1"
    assert documents[0].metadata["fichier"] == "file.md"
    assert documents[0].metadata["chunk_id"] == "file.md_0"
    assert documents[1].page_content == "Chunk 2"
    assert documents[1].metadata["fichier"] == "file.md"
    assert documents[1].metadata["chunk_id"] == "file.md_1"


# ===== TESTS POUR index_data =====

@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
def test_index_force_reindex(mock_save, mock_add, mock_get_store, mock_prepare, mock_list):
    """On peut forcer une reindexation complete de tous les fichiers."""
    mock_list.return_value = {"file1.md": 1000, "file2.txt": 2000}
    mock_prepare.return_value = [
        Document(page_content="Chunk", metadata={"fichier": "file1.md"})
    ]
    mock_get_store.return_value = Mock()

    result = index_data(force_reindex=True)

    assert result is True
    mock_prepare.assert_called_once()
    mock_get_store.assert_called_once_with(force_reindex=True)
    mock_add.assert_called_once()
    mock_save.assert_called_once()


@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_index_nouveaux_fichiers(mock_bm25, mock_save, mock_add, mock_prepare,
                                mock_get_store, mock_load, mock_list):
    """Les nouveaux fichiers sont detectes et indexes.
    prepare_files_for_ai est appelé deux fois : une pour indexer les nouveaux,
    une pour reconstruire le corpus BM25 complet.
    """
    mock_list.return_value = {"file1.md": 1000, "file2.txt": 2000}
    mock_load.return_value = {"file1.md": 1000}  # file2.txt est nouveau
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = [
        Document(page_content="New chunk", metadata={"fichier": "file2.txt"})
    ]

    result = index_data(force_reindex=False)

    assert result is True
    # Premier appel : indexation des nouveaux fichiers seulement
    assert mock_prepare.call_args_list[0] == (({'file2.txt'},),)
    # Deuxième appel : reconstruction BM25 sur les fichiers inchangés (file1.md)
    assert mock_prepare.call_args_list[1] == (({'file1.md'},),)
    mock_add.assert_called_once()
    mock_save.assert_called_once()


@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.remove_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_index_fichiers_modifies(mock_bm25, mock_save, mock_add, mock_prepare,
                                mock_remove, mock_get_store, mock_load, mock_list):
    """Les fichiers modifies sont reindexes (supprimes puis ajoutes).
    prepare_files_for_ai est appelé deux fois : une pour les modifiés,
    une pour reconstruire le corpus BM25 complet.
    """
    mock_list.return_value = {"file.md": 2000}
    mock_load.return_value = {"file.md": 1000}  # Modifie (timestamp plus recent)
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = [
        Document(page_content="Updated", metadata={"fichier": "file.md"})
    ]

    result = index_data(force_reindex=False)

    assert result is True
    mock_remove.assert_called_once()  # Supprime l'ancienne version
    # Premier appel : indexation du fichier modifié
    assert mock_prepare.call_args_list[0] == (({'file.md'},),)
    # Deuxième appel : reconstruction BM25 sur les fichiers inchangés (aucun ici)
    assert mock_prepare.call_args_list[1] == ((set(),),)
    mock_add.assert_called_once()  # Ajoute la nouvelle version
