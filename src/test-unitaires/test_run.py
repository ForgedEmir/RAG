"""
Tests unitaires pour le module run (orchestration de l'ingestion)
Teste les fonctions load_memory, save_memory, list_current_files, prepare_files_for_ai, et index_data.
Version LangChain + Qdrant.
"""
from unittest.mock import Mock, patch, mock_open
from langchain_core.documents import Document

from src.ingestion.run import (
    load_memory,
    save_memory,
    list_current_files,
    prepare_files_for_ai,
    index_data,
    MEMORY_FILE
)


# ===== TESTS POUR load_memory =====

@patch('os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='{"file.md": 1234567890, "doc.txt": 9876543210}')
def test_load_memory_existe_ancien_format(mock_file, mock_exists):
    """Compat ascendante : l'ancien format {nom: mtime_float} est migré vers
    {nom: {mtime, indexed_at}}. indexed_at = mtime en fallback (on n'a pas mieux)."""
    mock_exists.return_value = True

    memory = load_memory()

    assert memory == {
        "file.md": {"mtime": 1234567890.0, "indexed_at": 1234567890.0},
        "doc.txt": {"mtime": 9876543210.0, "indexed_at": 9876543210.0},
    }
    mock_exists.assert_called_once_with(MEMORY_FILE)
    mock_file.assert_called_once_with(MEMORY_FILE, 'r', encoding='utf-8')


@patch('os.path.exists')
@patch(
    'builtins.open',
    new_callable=mock_open,
    read_data='{"file.md": {"mtime": 1000, "indexed_at": 500}}',
)
def test_load_memory_nouveau_format(mock_file, mock_exists):
    """Le nouveau format {nom: {mtime, indexed_at}} est lu tel quel."""
    mock_exists.return_value = True

    memory = load_memory()

    assert memory == {"file.md": {"mtime": 1000.0, "indexed_at": 500.0}}


# ===== TESTS POUR save_memory =====

@patch('os.makedirs')
@patch('builtins.open', new_callable=mock_open)
def test_save_memory(mock_file, mock_makedirs):
    """On peut sauvegarder la memoire dans un fichier JSON."""
    fichiers = {"histoire.md": 1111111111, "personnages.txt": 2222222222}

    save_memory(fichiers)

    mock_makedirs.assert_called_once()
    mock_file.assert_called_once_with(MEMORY_FILE, 'w', encoding='utf-8')
    handle = mock_file()
    written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert "histoire.md" in written_content
    assert "personnages.txt" in written_content


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
@patch('src.ingestion.run._get_doc_context', return_value={"doc_summary": "", "entities": []})
@patch('src.ingestion.run._is_lore_content', return_value=True)
def test_prepare_files_ok(mock_is_lore, mock_ctx, mock_split, mock_clean, mock_extract, mock_exists):
    """On peut preparer des fichiers: extraction, nettoyage, decoupage."""
    mock_exists.return_value = True
    mock_extract.return_value = "Texte brut du fichier"
    mock_clean.return_value = "Texte nettoye"
    mock_split.return_value = ["Chunk 1", "Chunk 2"]

    documents = prepare_files_for_ai({"file.md"})

    assert len(documents) == 2
    assert isinstance(documents[0], Document)
    # page_content = texte contextuel (late chunking) ; original_text = chunk brut
    assert documents[0].metadata["original_text"] == "Chunk 1"
    assert documents[0].metadata["fichier"] == "file.md"
    assert documents[0].metadata["chunk_id"] == "file.md_0"
    assert documents[1].metadata["original_text"] == "Chunk 2"
    assert documents[1].metadata["fichier"] == "file.md"
    assert documents[1].metadata["chunk_id"] == "file.md_1"
    assert "chunk_sha256" in documents[0].metadata


@patch('src.ingestion.run.PARSER_MODE', 'custom')
@patch('os.path.exists')
@patch('src.ingestion.run.extract_text_from_file')
@patch('src.ingestion.run.clean_text')
@patch('src.ingestion.run.split_into_chunks')
@patch('src.ingestion.run._get_doc_context', return_value={"doc_summary": "", "entities": []})
@patch('src.ingestion.run._is_lore_content', return_value=True)
def test_prepare_files_dedup_sha256(mock_is_lore, mock_ctx, mock_split, mock_clean, mock_extract, mock_exists):
    """Deux chunks identiques ne doivent être indexés qu'une seule fois."""
    mock_exists.return_value = True
    mock_extract.return_value = "Texte brut"
    mock_clean.return_value = "Texte nettoye"
    mock_split.return_value = ["Chunk identique", "Chunk identique", "Chunk unique"]

    documents = prepare_files_for_ai({"file.md"})

    assert len(documents) == 2
    assert documents[0].metadata["original_text"] == "Chunk identique"
    assert documents[1].metadata["original_text"] == "Chunk unique"
    assert documents[0].metadata["chunk_sha256"] != ""


# ===== TESTS POUR index_data =====

@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_index_force_reindex(mock_bm25, mock_save, mock_add, mock_get_store, mock_prepare, mock_list):
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
    mock_bm25.assert_called_once()
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
    mock_load.return_value = {"file1.md": {"mtime": 1000, "indexed_at": 900}}
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = [
        Document(page_content="New chunk", metadata={"fichier": "file2.txt"})
    ]

    result = index_data(force_reindex=False)

    assert result is True
    # Premier appel : indexation des nouveaux fichiers seulement
    assert mock_prepare.call_args_list[0][0][0] == {"file2.txt"}
    # Deuxième appel : reconstruction BM25 sur les fichiers inchangés (file1.md)
    assert mock_prepare.call_args_list[1][0][0] == {"file1.md"}
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
    mock_load.return_value = {"file.md": {"mtime": 1000, "indexed_at": 500}}
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = [
        Document(page_content="Updated", metadata={"fichier": "file.md"})
    ]

    result = index_data(force_reindex=False)

    assert result is True
    mock_remove.assert_called_once()  # Supprime l'ancienne version
    # Premier appel : indexation du fichier modifié
    assert mock_prepare.call_args_list[0][0][0] == {"file.md"}
    # Deuxième appel : reconstruction BM25 sur les fichiers inchangés (aucun ici)
    assert mock_prepare.call_args_list[1][0][0] == set()
    mock_add.assert_called_once()  # Ajoute la nouvelle version


# ===== TESTS POUR l'invalidation du semantic cache (#174) =====

@patch('src.caching.semantic_cache.invalidate_for_files')
@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.remove_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_index_invalide_semantic_cache_sur_modif(
    mock_bm25, mock_save, mock_add, mock_prepare, mock_remove,
    mock_get_store, mock_load, mock_list, mock_invalidate,
):
    """Quand un fichier change, index_data() doit invalider le semantic cache ciblé."""
    mock_list.return_value = {"file.md": 2000, "autre.md": 500}
    mock_load.return_value = {
        "file.md":  {"mtime": 1000, "indexed_at": 100},
        "autre.md": {"mtime": 500,  "indexed_at": 100},
    }  # file.md modifié
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = [Document(page_content="x", metadata={"fichier": "file.md"})]

    index_data(force_reindex=False)

    mock_invalidate.assert_called_once()
    fichiers_invalides = mock_invalidate.call_args[0][0]
    assert fichiers_invalides == {"file.md"}


@patch('src.caching.semantic_cache.invalidate_for_files')
@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.remove_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_index_invalide_semantic_cache_sur_nouveau_fichier(
    mock_bm25, mock_save, mock_add, mock_prepare, mock_remove,
    mock_get_store, mock_load, mock_list, mock_invalidate,
):
    """Un nouveau fichier peut contredire une réponse cachée → invalidation ciblée."""
    mock_list.return_value = {"ancien.md": 1000, "nouveau.md": 2000}
    mock_load.return_value = {"ancien.md": {"mtime": 1000, "indexed_at": 100}}
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = [Document(page_content="x", metadata={"fichier": "nouveau.md"})]

    index_data(force_reindex=False)

    mock_invalidate.assert_called_once()
    assert mock_invalidate.call_args[0][0] == {"nouveau.md"}


@patch('src.caching.semantic_cache.invalidate_for_files')
@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.remove_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_index_invalide_semantic_cache_sur_suppression(
    mock_bm25, mock_save, mock_add, mock_prepare, mock_remove,
    mock_get_store, mock_load, mock_list, mock_invalidate,
):
    """Un fichier supprimé : on doit invalider les réponses qui s'y référaient."""
    mock_list.return_value = {"reste.md": 1000}
    mock_load.return_value = {
        "reste.md":  {"mtime": 1000, "indexed_at": 100},
        "retire.md": {"mtime": 500,  "indexed_at": 50},
    }
    mock_get_store.return_value = Mock()
    mock_prepare.return_value = []

    index_data(force_reindex=False)

    mock_invalidate.assert_called_once()
    assert mock_invalidate.call_args[0][0] == {"retire.md"}


@patch('src.caching.semantic_cache.clear_all')
@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.get_store')
@patch('src.ingestion.run.add_documents')
@patch('src.ingestion.run.save_memory')
@patch('src.ingestion.run._save_bm25_corpus')
def test_force_reindex_vide_tout_le_semantic_cache(
    mock_bm25, mock_save, mock_add, mock_get_store, mock_prepare,
    mock_list, mock_clear_all,
):
    """force_reindex=True → tout le cache sémantique est vidé, pas seulement une partie."""
    mock_list.return_value = {"file.md": 1000}
    mock_prepare.return_value = [Document(page_content="x", metadata={"fichier": "file.md"})]
    mock_get_store.return_value = Mock()

    index_data(force_reindex=True)

    mock_clear_all.assert_called_once()
