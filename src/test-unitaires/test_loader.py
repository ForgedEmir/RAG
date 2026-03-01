"""
Tests unitaires simplifiés pour le module loader

Ce fichier teste la fonction qui ajoute des textes dans ChromaDB.
Note : On utilise des "mocks" pour simuler ChromaDB sans vraiment l'utiliser.
"""

# Import de unittest.mock pour simuler des objets
from unittest.mock import Mock, MagicMock
import sys

# On simule fastembed pour éviter de télécharger le modèle (plusieurs Go)
sys.modules['fastembed'] = MagicMock()
sys.modules['fastembed.TextEmbedding'] = MagicMock()

# Import de la fonction à tester
from src.ingestion.loader import add_to_chromadb


# ===== TESTS POUR add_to_chromadb =====

def test_ajouter_chunks_simples():
    """On peut ajouter des morceaux de texte simples."""
    # On crée une fausse collection avec Mock
    collection_simulee = Mock()
    
    # On prépare des morceaux de texte
    chunks = [
        {"texte": "Premier morceau", "fichier": "test.md"},
        {"texte": "Deuxième morceau", "fichier": "test.md"}
    ]
    
    # On appelle la fonction
    add_to_chromadb(collection_simulee, chunks)
    
    # On vérifie que la fonction add() de la collection a été appelée
    assert collection_simulee.add.called == True
    
    # On vérifie qu'on a bien 2 morceaux
    appel = collection_simulee.add.call_args
    assert len(appel.kwargs['documents']) == 2


def test_ajouter_chunks_vides():
    """Avec une liste vide, rien ne se passe."""
    collection_simulee = Mock()
    chunks = []
    
    # On appelle avec une liste vide
    add_to_chromadb(collection_simulee, chunks)
    
    # La fonction add() ne devrait pas être appelée
    assert collection_simulee.add.called == False


def test_ids_uniques_generes():
    """Chaque morceau reçoit un ID unique."""
    collection_simulee = Mock()
    chunks = [
        {"texte": "Texte 1", "fichier": "test.md"},
        {"texte": "Texte 2", "fichier": "test.md"}
    ]
    
    add_to_chromadb(collection_simulee, chunks)
    
    # On récupère les arguments de l'appel à add()
    appel = collection_simulee.add.call_args
    ids_generes = appel.kwargs['ids']  # Les IDs passés à add()
    
    # Les IDs doivent être uniques
    assert len(ids_generes) == 2
    assert ids_generes[0] != ids_generes[1]


def test_metadonnees_correctes():
    """Les métadonnées (nom du fichier) sont bien transmises."""
    collection_simulee = Mock()
    chunks = [
        {"texte": "Contenu", "fichier": "histoire.md"}
    ]
    
    add_to_chromadb(collection_simulee, chunks)
    
    # On récupère les métadonnées
    appel = collection_simulee.add.call_args
    metadonnees = appel.kwargs['metadatas']
    
    # Le nom du fichier doit être présent
    assert metadonnees[0]['fichier'] == "histoire.md"


def test_textes_preserves():
    """Les textes sont bien transmis à ChromaDB."""
    collection_simulee = Mock()
    chunks = [
        {"texte": "Mon super texte", "fichier": "test.md"}
    ]
    
    add_to_chromadb(collection_simulee, chunks)
    
    # On récupère les documents (textes)
    appel = collection_simulee.add.call_args
    textes = appel.kwargs['documents']
    
    # Le texte doit être intact
    assert textes[0] == "Mon super texte"


def test_plusieurs_fichiers():
    """On peut ajouter des morceaux de fichiers différents."""
    collection_simulee = Mock()
    chunks = [
        {"texte": "Texte 1", "fichier": "file1.md"},
        {"texte": "Texte 2", "fichier": "file2.md"}
    ]
    
    add_to_chromadb(collection_simulee, chunks)
    
    # La fonction add() doit être appelée une fois
    assert collection_simulee.add.call_count == 1
    
    # Avec 2 morceaux
    appel = collection_simulee.add.call_args
    assert len(appel.kwargs['documents']) == 2


def test_format_id():
    """Les IDs contiennent le nom du fichier."""
    collection_simulee = Mock()
    chunks = [
        {"texte": "Contenu", "fichier": "test.md"}
    ]
    
    add_to_chromadb(collection_simulee, chunks)
    
    appel = collection_simulee.add.call_args
    id_genere = appel.kwargs['ids'][0]
    
    # L'ID doit contenir le nom du fichier
    assert "test.md" in id_genere
