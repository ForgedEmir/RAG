"""
Tests unitaires pour le module run (orchestration de l'ingestion)
Teste les fonctions load_memory, save_memory, list_current_files, prepare_files_for_ai, et index_data.
"""

import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from dataclasses import dataclass
from typing import List

from src.ingestion.run import (
    load_memory,
    save_memory,
    list_current_files,
    prepare_files_for_ai,
    index_data,
    MEMORY_FILE,
    DATA_FOLDER
)


# Copie de ValidationResult pour ne pas importer validator dans les tests
@dataclass
class ValidationResult:
    is_valid: bool
    filepath: str
    errors: List[str]
    warnings: List[str]


# Note importante pour les débutants :
# Ces tests vérifient l'orchestration de l'ingestion des données.
# On simule les fichiers et ChromaDB pour ne pas toucher au vrai système.


# ===== TESTS POUR load_memory =====

@patch('os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='{"file.md": 1234567890, "doc.txt": 9876543210}')
def test_load_memory_existe(mock_file, mock_exists):
    """On peut charger la mémoire depuis le fichier JSON."""
    mock_exists.return_value = True
    
    memory = load_memory()
    
    assert memory == {"file.md": 1234567890, "doc.txt": 9876543210}
    mock_exists.assert_called_once_with(MEMORY_FILE)
    mock_file.assert_called_once_with(MEMORY_FILE, 'r', encoding='utf-8')


# ===== TESTS POUR save_memory =====

@patch('os.makedirs')
@patch('builtins.open', new_callable=mock_open)
def test_save_memory(mock_file, mock_makedirs):
    """On peut sauvegarder la mémoire dans un fichier JSON."""
    fichiers = {"histoire.md": 1111111111, "personnages.txt": 2222222222}
    
    save_memory(fichiers)
    
    mock_makedirs.assert_called_once()
    mock_file.assert_called_once_with(MEMORY_FILE, 'w', encoding='utf-8')
    # Vérifie que le contenu est écrit
    handle = mock_file()
    written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
    assert "histoire.md" in written_content
    assert "personnages.txt" in written_content


# ===== TESTS POUR list_current_files =====

@patch('os.path.exists')
@patch('os.listdir')
@patch('os.path.getmtime')
def test_list_current_files_ok(mock_getmtime, mock_listdir, mock_exists):
    """On peut lister les fichiers supportés avec leur date de modification."""
    mock_exists.return_value = True
    mock_listdir.return_value = ["file1.md", "file2.txt", "image.png", "DOC.MD"]
    mock_getmtime.side_effect = [1000, 2000, 3000, 4000]
    
    fichiers = list_current_files()
    
    # image.png n'est pas supporté, mais les autres oui (y compris DOC.MD en majuscules)
    assert len(fichiers) == 3
    assert "file1.md" in fichiers
    assert "file2.txt" in fichiers
    assert "DOC.MD" in fichiers
    assert "image.png" not in fichiers


# ===== TESTS POUR prepare_files_for_ai =====

@patch('src.ingestion.run.validate_file')
@patch('os.path.exists')
@patch('src.ingestion.run.extract_text_from_file')
@patch('src.ingestion.run.clean_text')
@patch('src.ingestion.run.split_into_chunks')
def test_prepare_files_ok(mock_split, mock_clean, mock_extract, mock_exists, mock_validate):
    """On peut préparer des fichiers: extraction, nettoyage, découpage."""
    mock_exists.return_value = True
    # Créer un ValidationResult valide
    mock_validate.return_value = ValidationResult(
        is_valid=True,
        filepath="data/sample/file.md",
        errors=[],
        warnings=[]
    )
    mock_extract.return_value = "Texte brut du fichier"
    mock_clean.return_value = "Texte nettoyé"
    mock_split.return_value = ["Chunk 1", "Chunk 2"]
    
    morceaux = prepare_files_for_ai({"file.md"})
    
    assert len(morceaux) == 2
    assert morceaux[0] == {"texte": "Chunk 1", "fichier": "file.md"}
    assert morceaux[1] == {"texte": "Chunk 2", "fichier": "file.md"}


# ===== TESTS POUR index_data =====

@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.store_in_chromadb')
@patch('src.ingestion.run.save_memory')
def test_index_force_reindex(mock_save, mock_store, mock_prepare, mock_list):
    """On peut forcer une réindexation complète de tous les fichiers."""
    mock_list.return_value = {"file1.md": 1000, "file2.txt": 2000}
    mock_prepare.return_value = [{"texte": "Chunk", "fichier": "file1.md"}]
    
    result = index_data(force_reindex=True)
    
    assert result is True
    mock_prepare.assert_called_once()
    mock_store.assert_called_once_with([{"texte": "Chunk", "fichier": "file1.md"}], force_reindex=True)
    mock_save.assert_called_once()


@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run._get_collection')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_to_chromadb')
@patch('src.ingestion.run.save_memory')
def test_index_nouveaux_fichiers(mock_save, mock_add, mock_prepare, 
                                mock_get_col, mock_load, mock_list):
    """Les nouveaux fichiers sont détectés et indexés."""
    mock_list.return_value = {"file1.md": 1000, "file2.txt": 2000}
    mock_load.return_value = {"file1.md": 1000}  # file2.txt est nouveau
    mock_get_col.return_value = MagicMock()
    mock_prepare.return_value = [{"texte": "New chunk", "fichier": "file2.txt"}]
    
    result = index_data(force_reindex=False)
    
    assert result is True
    # Vérifie qu'on prépare seulement le nouveau fichier
    mock_prepare.assert_called_once_with({"file2.txt"})
    mock_add.assert_called_once()
    mock_save.assert_called_once()


@patch('src.ingestion.run.list_current_files')
@patch('src.ingestion.run.load_memory')
@patch('src.ingestion.run._get_collection')
@patch('src.ingestion.run.remove_files_from_chromadb')
@patch('src.ingestion.run.prepare_files_for_ai')
@patch('src.ingestion.run.add_to_chromadb')
@patch('src.ingestion.run.save_memory')
def test_index_fichiers_modifies(mock_save, mock_add, mock_prepare,
                                mock_remove, mock_get_col, mock_load, mock_list):
    """Les fichiers modifiés sont réindexés (supprimés puis ajoutés)."""
    mock_list.return_value = {"file.md": 2000}
    mock_load.return_value = {"file.md": 1000}  # Modifié (timestamp plus récent)
    mock_get_col.return_value = MagicMock()
    mock_prepare.return_value = [{"texte": "Updated", "fichier": "file.md"}]
    
    result = index_data(force_reindex=False)
    
    assert result is True
    mock_remove.assert_called_once()  # Supprime l'ancienne version
    mock_prepare.assert_called_once_with({"file.md"})
    mock_add.assert_called_once()  # Ajoute la nouvelle version
