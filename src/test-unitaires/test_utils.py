"""
Tests unitaires pour le module utils

Ce fichier teste les fonctions utilitaires (validation, nettoyage, formatage).
Chaque fonction est simple et testée individuellement.
"""

# On importe toutes les fonctions à tester
from src.utils import (
    valider_question,
    nettoyer_texte,
    formater_nom_fichier,
    extraire_extension,
    compter_mots,
    tronquer_texte
)


# ===== TESTS POUR valider_question =====

def test_valider_question_ok():
    """Une question normale devrait être valide."""
    assert valider_question("Qui est le héros?") == True


def test_valider_question_vide():
    """Une question vide n'est pas valide."""
    assert valider_question("") == False


# ===== TESTS POUR nettoyer_texte =====

def test_nettoyer_texte_espaces_multiples():
    """Les espaces multiples deviennent un seul espace."""
    texte = "Texte  avec   beaucoup    d'espaces"
    assert nettoyer_texte(texte) == "Texte avec beaucoup d'espaces"


# ===== TESTS POUR formater_nom_fichier =====

def test_formater_fichier_md():
    """Enlève l'extension .md d'un fichier."""
    assert formater_nom_fichier("document.md") == "document"


# ===== TESTS POUR extraire_extension =====

def test_extraire_extension_md():
    """Extrait l'extension md."""
    assert extraire_extension("document.md") == "md"


# ===== TESTS POUR compter_mots =====

def test_compter_mots_simple():
    """Compte les mots d'un texte simple."""
    assert compter_mots("un deux trois") == 3


# ===== TESTS POUR tronquer_texte =====

def test_tronquer_texte_long():
    """Un texte trop long est tronqué avec '...'."""
    texte = "A" * 150
    resultat = tronquer_texte(texte, 100)
    # 100 caractères + "..." = 103
    assert len(resultat) == 103
    assert resultat.endswith("...")
