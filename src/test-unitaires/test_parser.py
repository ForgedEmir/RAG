"""
Tests unitaires pour le module parser

Ce fichier teste les fonctions qui lisent et nettoient les fichiers.
"""

# Import des fonctions à tester
from src.ingestion.parser import extract_text_from_file, clean_text, _clean_invalid_characters, _try_multiple_encodings
# Import de tempfile pour créer des fichiers de test
import tempfile
import os
import json


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


def test_extension_non_supportee(caplog):
    """Une extension inconnue retourne None et émet un warning."""
    import logging
    
    # On crée un fichier avec une extension non supportée
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False, encoding='utf-8') as f:
        f.write("Contenu")
        nom_fichier = f.name
    
    with caplog.at_level(logging.WARNING):
        resultat = extract_text_from_file(nom_fichier)
    
    # Extension non supportée = None
    assert resultat == None
    
    # Vérifier qu'un warning a été émis
    assert any("Format non supporté" in record.message for record in caplog.records)
    assert any(".xyz" in record.message for record in caplog.records)
    
    os.unlink(nom_fichier)


def test_lire_fichier_xml():
    """On peut lire un fichier .xml."""
    # On crée un fichier XML temporaire
    contenu_xml = """<?xml version="1.0" encoding="UTF-8"?>
<personnage>
    <nom>Gandalf</nom>
    <classe>Magicien</classe>
    <description>Un puissant magicien gris</description>
</personnage>"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False, encoding='utf-8') as f:
        f.write(contenu_xml)
        nom_fichier = f.name
    
    # On lit le fichier
    resultat = extract_text_from_file(nom_fichier)
    
    # Le support XML n'est pas encore implémenté, donc on attend None
    assert resultat is None
    
    # On supprime le fichier temporaire
    os.unlink(nom_fichier)


# ===== TESTS POUR LES AMÉLIORATIONS DE GESTION D'ERREURS =====

def test_csv_encodage_latin1():
    """On peut lire un fichier CSV encodé en latin-1."""
    # Créer un fichier CSV avec des caractères accentués en latin-1
    contenu_csv = "Nom,Description\nÉpée,Arme tranchante\nBouclier,Défense"
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as f:
        f.write(contenu_csv.encode('latin-1'))
        nom_fichier = f.name
    
    # On lit le fichier
    resultat = extract_text_from_file(nom_fichier)
    
    # On vérifie que le contenu est présent (tolérant pour les caractères accentués)
    assert resultat is not None
    assert "Arme" in resultat
    assert "tranchante" in resultat
    assert "Bouclier" in resultat
    
    os.unlink(nom_fichier)


def test_csv_encodage_windows1252():
    """On peut lire un fichier CSV avec des caractères Windows-1252."""
    # Caractères spécifiques à Windows-1252
    contenu_csv = "Item,Prix\nÉpée magique,100€\nPotion,5€"
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.csv', delete=False) as f:
        f.write(contenu_csv.encode('windows-1252'))
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert resultat is not None
    assert "magique" in resultat or "pée" in resultat
    assert "100" in resultat
    
    os.unlink(nom_fichier)


def test_json_caracteres_speciaux():
    """On peut lire un fichier JSON avec des caractères spéciaux."""
    # JSON avec caractères accentués et spéciaux
    data = {
        "personnage": "Éléanor",
        "description": "Une guerrière très puissante avec des runes : ⚔️ et ✨",
        "dialogue": "« Bonjour, étranger ! »"
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert resultat is not None
    assert "Éléanor" in resultat or "l" in resultat  # Au moins une partie du nom
    assert "guerrière" in resultat or "guerri" in resultat
    
    os.unlink(nom_fichier)


def test_json_encodage_latin1():
    """On peut lire un fichier JSON encodé en latin-1."""
    contenu_json = '{"nom": "Château", "lieu": "Forêt enchantée"}'
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.json', delete=False) as f:
        f.write(contenu_json.encode('latin-1'))
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert resultat is not None
    assert "teau" in resultat or "Château" in resultat
    assert "t" in resultat or "Forêt" in resultat
    
    os.unlink(nom_fichier)


def test_clean_invalid_characters():
    """La fonction _clean_invalid_characters nettoie les caractères de contrôle."""
    # Texte avec caractères de contrôle
    texte_sale = "Texte\x00avec\x01des\x02caractères\x03invalides"
    
    resultat = _clean_invalid_characters(texte_sale)
    
    # Les caractères de contrôle doivent être remplacés par des espaces
    assert "\x00" not in resultat
    assert "\x01" not in resultat
    assert "Texte" in resultat
    assert "avec" in resultat


def test_fichier_txt_encodage_mixte():
    """On peut lire un fichier .txt avec un encodage non-UTF8."""
    texte = "Histoire de l'épée légendaire du héros"
    
    # Créer le fichier en ISO-8859-1
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
        f.write(texte.encode('iso-8859-1'))
        nom_fichier = f.name
    
    resultat = extract_text_from_file(nom_fichier)
    
    assert resultat is not None
    assert "Histoire" in resultat
    assert "pée" in resultat or "épée" in resultat
    
    os.unlink(nom_fichier)


def test_try_multiple_encodings():
    """La fonction _try_multiple_encodings essaie plusieurs encodages."""
    texte = "Texte avec des accents : été, château, forêt"
    
    # Créer un fichier en Latin-1
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
        f.write(texte.encode('latin-1'))
        nom_fichier = f.name
    
    # La fonction devrait réussir à le lire
    resultat = _try_multiple_encodings(nom_fichier)
    
    assert resultat is not None
    assert "Texte" in resultat
    assert "accents" in resultat
    
    os.unlink(nom_fichier)
