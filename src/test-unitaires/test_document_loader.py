"""
Tests unitaires pour le module document_loader (Unstructured.io via LangChain)

Ce fichier teste les fonctions de chargement de documents avec Unstructured.
"""
from unittest.mock import Mock, patch, MagicMock
from langchain_core.documents import Document


# ===== TESTS POUR load_document =====

@patch('os.path.exists')
def test_load_document_ok(mock_exists):
    """On peut charger un document avec le TextLoader LangChain."""
    with patch('src.ingestion.document_loader.clean_text', return_value="Texte nettoye"):
        mock_exists.return_value = True
        mock_loader = Mock()
        mock_loader.load.return_value = [
            Document(page_content="Texte brut du fichier", metadata={"source": "test.md"})
        ]

        with patch('langchain_community.document_loaders.TextLoader', return_value=mock_loader):
            from src.ingestion.document_loader import load_document
            docs = load_document("test.md")

        assert len(docs) == 1
        assert docs[0].page_content == "Texte nettoye"


@patch('os.path.exists')
def test_load_document_fichier_inexistant(mock_exists):
    """Un fichier inexistant retourne une liste vide."""
    mock_exists.return_value = False

    from src.ingestion.document_loader import load_document
    docs = load_document("inexistant.md")

    assert docs == []


# ===== TESTS POUR extract_text_with_unstructured =====

@patch('src.ingestion.document_loader.load_document')
def test_extract_text_ok(mock_load):
    """On peut extraire du texte avec la fonction compatible."""
    mock_load.return_value = [
        Document(page_content="Partie 1", metadata={}),
        Document(page_content="Partie 2", metadata={})
    ]

    from src.ingestion.document_loader import extract_text_with_unstructured
    texte = extract_text_with_unstructured("test.md")

    assert texte == "Partie 1\n\nPartie 2"


@patch('src.ingestion.document_loader.load_document')
def test_extract_text_vide(mock_load):
    """Si le document est vide, retourne None."""
    mock_load.return_value = []

    from src.ingestion.document_loader import extract_text_with_unstructured
    texte = extract_text_with_unstructured("vide.md")

    assert texte is None
