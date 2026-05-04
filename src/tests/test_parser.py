"""
Tests unitaires pour le module parser

Ce fichier teste les fonctions qui lisent et nettoient les fichiers.
"""

# Import functions to test
from src.ingestion.parser import extract_text_from_file, clean_text
# Import tempfile to create test files
import tempfile
import os


# ===== TESTS POUR clean_text =====

def test_texte_propre():
    """Un texte propre reste propre."""
    texte = "Ceci est un texte propre"
    resultat = clean_text(texte)
    
    assert resultat == texte


def test_enlever_balises_html():
    """HTML tags are removed."""
    texte = "<p>Paragraphe avec <strong>gras</strong></p>"
    resultat = clean_text(texte)
    
    # Les balises disparaissent mais le texte reste
    assert "<p>" not in resultat
    assert "Paragraphe" in resultat
    assert "gras" in resultat


def test_remplacer_player_name():
    """The %PLAYER_NAME% variable is replaced."""
    texte = "Hello %PLAYER_NAME%, bienvenue!"
    resultat = clean_text(texte)
    
    assert "%PLAYER_NAME%" not in resultat
    assert "the player" in resultat


def test_normaliser_espaces():
    """Les espaces multiples deviennent un seul espace."""
    texte = "Texte  avec   beaucoup    d'espaces"
    resultat = clean_text(texte)
    
    # Plus d'espaces doubles
    assert "  " not in resultat
    assert resultat == "Texte avec beaucoup d'espaces"


# ===== TESTS POUR extract_text_from_file =====

def test_read_txt_file():
    """On peut lire un fichier .txt."""
    # We create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Ceci est un test")
        nom_fichier = f.name
    
    # On lit le fichier
    resultat = extract_text_from_file(nom_fichier)
    
    # We check the content
    assert resultat == "Ceci est un test"
    
    # On supprime le fichier temporaire
    os.unlink(nom_fichier)


def test_missing_file():
    """Un fichier qui n'existe pas retourne None."""
    resultat = extract_text_from_file("fichier_qui_nexiste_pas.txt")
    
    assert resultat is None


def test_extension_non_supportee():
    """Une extension inconnue retourne None."""
    # We create a file with an unsupported extension
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False, encoding='utf-8') as f:
        f.write("Contenu")
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    # Unsupported extension = None
    assert resultat is None
    
    os.unlink(nom_fichier)


def test_read_xml_file():
    """An .xml file must be read and cleaned of its tags."""
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<racine>
    <titre>Le grand test</titre>
    <contenu>
        <paragraphe>Ceci est une phrase.</paragraphe>
        <paragraphe>Une autre phrase vide : <vide></vide></paragraphe>
    </contenu>
</racine>
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    # We check that the tags have disappeared and the text is there
    assert "Le grand test" in resultat
    assert "Ceci est une phrase." in resultat
    assert "Une autre phrase vide :" in resultat
    # Tags must not be present
    assert "<titre>" not in resultat
    assert "<paragraphe>" not in resultat
    
    os.unlink(nom_fichier)

def test_read_corrupted_xml_file():
    """A malformed .xml file should not crash — returns empty string or partial text."""
    xml_content = "<root><title>No closing tag"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name

    resultat = extract_text_from_file(nom_fichier)

    # Must not raise an exception; result is a string (may be empty or partial)
    assert isinstance(resultat, (str, type(None)))

    os.unlink(nom_fichier)

def test_read_xml_file_with_attributes():
    """Un fichier XML avec des attributs ne doit extraire que le texte, pas les attributs."""
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<donjon>
    <monstres>
        <monster level="5" type="flying">Giant bat</monster>
    </monstres>
</donjon>
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert "Giant bat" in resultat or "bat" in resultat.lower()
    assert "level" not in resultat
    assert "flying" not in resultat
    assert "5" not in resultat
    
    os.unlink(nom_fichier)

def test_read_empty_xml_file():
    """An .xml file without text content should not crash."""
    xml_content = "<root><empty></empty><other/></root>"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name

    resultat = extract_text_from_file(nom_fichier)

    # Must not raise an exception; result is a string (may be empty)
    assert isinstance(resultat, (str, type(None)))

    os.unlink(nom_fichier)
