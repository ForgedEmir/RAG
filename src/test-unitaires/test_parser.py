"""
Tests unitaires pour le module parser

Ce fichier teste les fonctions qui lisent et nettoient les fichiers.
"""

# Import des fonctions à tester
from src.ingestion.parser import extract_text_from_file, clean_text
# Import de tempfile pour créer des fichiers de test
import tempfile
import os


# ===== TESTS POUR clean_text =====

def test_texte_propre():
    """Un texte propre reste propre."""
    texte = "Ceci est un texte propre"
    resultat = clean_text(texte)
    
    assert resultat == texte


def test_enlever_balises_html():
    """Les balises HTML sont enlevées."""
    texte = "<p>Paragraphe avec <strong>gras</strong></p>"
    resultat = clean_text(texte)
    
    # Les balises disparaissent mais le texte reste
    assert "<p>" not in resultat
    assert "Paragraphe" in resultat
    assert "gras" in resultat


def test_remplacer_player_name():
    """La variable %PLAYER_NAME% est remplacée."""
    texte = "Bonjour %PLAYER_NAME%, bienvenue!"
    resultat = clean_text(texte)
    
    # %PLAYER_NAME% devient "le joueur"
    assert "%PLAYER_NAME%" not in resultat
    assert "le joueur" in resultat


def test_normaliser_espaces():
    """Les espaces multiples deviennent un seul espace."""
    texte = "Texte  avec   beaucoup    d'espaces"
    resultat = clean_text(texte)
    
    # Plus d'espaces doubles
    assert "  " not in resultat
    assert resultat == "Texte avec beaucoup d'espaces"


# ===== TESTS POUR extract_text_from_file =====

def test_lire_fichier_txt():
    """On peut lire un fichier .txt."""
    # On crée un fichier temporaire
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Ceci est un test")
        nom_fichier = f.name
    
    # On lit le fichier
    resultat = extract_text_from_file(nom_fichier)
    
    # On vérifie le contenu
    assert resultat == "Ceci est un test"
    
    # On supprime le fichier temporaire
    os.unlink(nom_fichier)


def test_fichier_inexistant():
    """Un fichier qui n'existe pas retourne None."""
    resultat = extract_text_from_file("fichier_qui_nexiste_pas.txt")
    
    assert resultat == None


def test_extension_non_supportee():
    """Une extension inconnue retourne None."""
    # On crée un fichier avec une extension non supportée
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False, encoding='utf-8') as f:
        f.write("Contenu")
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    # Extension non supportée = None
    assert resultat == None
    
    os.unlink(nom_fichier)


def test_lire_fichier_xml():
    """Un fichier .xml doit être lu et nettoyé de ses balises."""
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
    
    # On vérifie que les balises ont disparu et que le texte est là
    assert "Le grand test" in resultat
    assert "Ceci est une phrase." in resultat
    assert "Une autre phrase vide :" in resultat
    # Les balises ne doivent pas être présentes
    assert "<titre>" not in resultat
    assert "<paragraphe>" not in resultat
    
    os.unlink(nom_fichier)

def test_lire_fichier_xml_corrompu():
    """Un fichier .xml mal formé ne doit pas crasher mais retourner une chaîne vide."""
    xml_content = "<racine><titre>Pas de balise fermante"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    # Doit retourner une chaîne vide et ne pas lever d'exception
    assert resultat == ""
    
    os.unlink(nom_fichier)

def test_lire_fichier_xml_attributs():
    """Un fichier XML avec des attributs ne doit extraire que le texte, pas les attributs."""
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<donjon>
    <monstres>
        <monstre niveau="5" type="volant">Chauve-souris géante</monstre>
    </monstres>
</donjon>
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert "Chauve-souris" in resultat
    assert "niveau" not in resultat
    assert "volant" not in resultat
    assert "5" not in resultat
    
    os.unlink(nom_fichier)

def test_lire_fichier_xml_vide():
    """Un fichier .xml sans texte retourne une chaîne vide."""
    xml_content = "<racine><vide></vide><autre/></racine>"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(xml_content)
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert resultat == ""
    
    os.unlink(nom_fichier)
