"""
Tests unitaires pour le module document_loader (Unstructured.io)

Ce fichier teste les fonctions de chargement de documents avec Unstructured.
On mocke la fonction _try_partition() pour eviter d'importer la librairie
Unstructured reellement (elle peut crasher sur Windows a cause de python-magic).
"""
from unittest.mock import Mock, patch
from langchain_core.documents import Document


# ===== TESTS POUR load_document =====

@patch('os.path.exists', return_value=True)
@patch('src.ingestion.document_loader.clean_text', side_effect=lambda t: t)
@patch('src.ingestion.document_loader._try_partition')
def test_load_document_ok(mock_partition, mock_clean, mock_exists):
    """Unstructured extrait les elements et on les convertit en Documents LangChain."""
    mock_elem1 = Mock()
    mock_elem1.text = "Le roi Alaric gouverne Aethelgard"
    mock_elem2 = Mock()
    mock_elem2.text = "Lady Elara est la magicienne de la cour"
    mock_partition.return_value = [mock_elem1, mock_elem2]

    from src.ingestion.document_loader import load_document
    docs = load_document("personnages.md")

    assert len(docs) == 2
    assert docs[0].page_content == "Le roi Alaric gouverne Aethelgard"
    assert docs[1].page_content == "Lady Elara est la magicienne de la cour"


@patch('os.path.exists', return_value=False)
def test_load_document_fichier_inexistant(mock_exists):
    """Un fichier inexistant retourne une liste vide."""
    from src.ingestion.document_loader import load_document
    docs = load_document("inexistant.md")

    assert docs == []


@patch('os.path.exists', return_value=True)
@patch('src.ingestion.document_loader.clean_text', return_value="Texte nettoye")
@patch('src.ingestion.document_loader._try_partition')
def test_load_document_applique_clean_text(mock_partition, mock_clean, mock_exists):
    """Le nettoyage clean_text() est bien applique sur chaque element."""
    mock_elem = Mock()
    mock_elem.text = "<b>Texte avec balises</b> et %PLAYER_NAME%"
    mock_partition.return_value = [mock_elem]

    from src.ingestion.document_loader import load_document
    docs = load_document("test.md")

    assert len(docs) == 1
    assert docs[0].page_content == "Texte nettoye"
    mock_clean.assert_called_once_with("<b>Texte avec balises</b> et %PLAYER_NAME%")


@patch('os.path.exists', return_value=True)
@patch('src.ingestion.document_loader.clean_text', return_value="Texte fallback nettoye")
@patch('src.ingestion.document_loader.extract_text_from_file', return_value="Texte du fallback")
@patch('src.ingestion.document_loader._try_partition', side_effect=Exception("Format inconnu"))
def test_load_document_fallback_si_unstructured_echoue(mock_partition, mock_extract, mock_clean, mock_exists):
    """Si Unstructured plante, on tombe sur le parser custom."""
    from src.ingestion.document_loader import load_document
    docs = load_document("fichier_bizarre.xyz")

    assert len(docs) == 1
    assert docs[0].page_content == "Texte fallback nettoye"
    mock_extract.assert_called_once()


@patch('os.path.exists', return_value=True)
@patch('src.ingestion.document_loader.clean_text', side_effect=lambda t: t.strip() if t.strip() else "")
@patch('src.ingestion.document_loader._try_partition')
def test_load_document_elements_vides_ignores(mock_partition, mock_clean, mock_exists):
    """Les elements dont le texte est vide apres nettoyage sont ignores."""
    mock_elem_vide = Mock()
    mock_elem_vide.text = "   "
    mock_elem_ok = Mock()
    mock_elem_ok.text = "Texte valide"
    mock_partition.return_value = [mock_elem_vide, mock_elem_ok]

    from src.ingestion.document_loader import load_document
    docs = load_document("test.md")

    assert len(docs) == 1
    assert docs[0].page_content == "Texte valide"


@patch('os.path.exists', return_value=True)
@patch('src.ingestion.document_loader.clean_text', return_value="Texte custom nettoye")
@patch('src.ingestion.document_loader.extract_text_from_file', return_value="Texte custom")
@patch('src.ingestion.document_loader._try_partition', return_value=[])
def test_load_document_fallback_si_partition_vide(mock_partition, mock_extract, mock_clean, mock_exists):
    """Si Unstructured retourne une liste vide, on tombe sur le fallback."""
    from src.ingestion.document_loader import load_document
    docs = load_document("vide.md")

    assert len(docs) == 1
    assert docs[0].page_content == "Texte custom nettoye"


# ===== TESTS POUR extract_text_with_unstructured =====

@patch('src.ingestion.document_loader.load_document')
def test_extract_text_ok(mock_load):
    """On peut extraire du texte et le concatener."""
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
