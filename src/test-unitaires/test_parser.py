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


def test_enlever_variables_jeu():
    """Les variables de jeu sont enlevées."""
    texte = "Quest %QUEST_NAME% et NPC %NP_NAME%"
    resultat = clean_text(texte)
    
    assert "%QUEST_NAME%" not in resultat
    assert "%NP_NAME%" not in resultat


def test_normaliser_espaces():
    """Les espaces multiples deviennent un seul espace."""
    texte = "Texte  avec   beaucoup    d'espaces"
    resultat = clean_text(texte)
    
    # Plus d'espaces doubles
    assert "  " not in resultat
    assert resultat == "Texte avec beaucoup d'espaces"


def test_texte_vide():
    """Un texte vide reste vide."""
    assert clean_text("") == ""


def test_texte_none():
    """None devient une chaîne vide."""
    assert clean_text(None) == ""


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


def test_lire_fichier_md():
    """On peut lire un fichier Markdown."""
    # On crée un fichier temporaire
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write("# Titre\n\nContenu")
        nom_fichier = f.name
    
    # On lit le fichier
    resultat = extract_text_from_file(nom_fichier)
    
    # On vérifie le contenu
    assert "Titre" in resultat
    assert "Contenu" in resultat
    
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


def test_fichier_avec_accents():
    """Les caractères spéciaux sont bien lus."""
    # On crée un fichier avec des accents
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write("Café élève où")
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    # Les accents sont préservés
    assert resultat == "Café élève où"
    
    os.unlink(nom_fichier)

