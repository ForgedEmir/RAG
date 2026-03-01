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


def test_valider_question_trop_courte():
    """Une question d'un seul caractère n'est pas valide."""
    assert valider_question("a") == False


def test_valider_question_deux_caracteres():
    """Deux caractères, c'est le minimum."""
    assert valider_question("ok") == True


def test_valider_question_avec_espaces():
    """Les espaces autour sont ignorés."""
    assert valider_question("  Qui?  ") == True


def test_valider_question_none():
    """None n'est pas une question valide."""
    assert valider_question(None) == False


def test_valider_question_nombre():
    """Un nombre n'est pas une question."""
    assert valider_question(123) == False


# ===== TESTS POUR nettoyer_texte =====

def test_nettoyer_texte_normal():
    """Un texte propre reste propre."""
    assert nettoyer_texte("Texte propre") == "Texte propre"


def test_nettoyer_texte_espaces_multiples():
    """Les espaces multiples deviennent un seul espace."""
    texte = "Texte  avec   beaucoup    d'espaces"
    assert nettoyer_texte(texte) == "Texte avec beaucoup d'espaces"


def test_nettoyer_texte_espaces_bords():
    """Les espaces au début et fin sont enlevés."""
    assert nettoyer_texte("   Texte   ") == "Texte"


def test_nettoyer_texte_vide():
    """Un texte vide reste vide."""
    assert nettoyer_texte("") == ""


def test_nettoyer_texte_tabulations():
    """Les tabulations deviennent des espaces."""
    assert nettoyer_texte("Texte\tavec\ttab") == "Texte avec tab"


def test_nettoyer_texte_sauts_ligne():
    """Les sauts de ligne deviennent des espaces."""
    assert nettoyer_texte("Ligne1\nLigne2") == "Ligne1 Ligne2"


def test_nettoyer_texte_none():
    """None devient une chaîne vide."""
    assert nettoyer_texte(None) == ""


# ===== TESTS POUR formater_nom_fichier =====

def test_formater_fichier_md():
    """Enlève l'extension .md d'un fichier."""
    assert formater_nom_fichier("document.md") == "document"


def test_formater_fichier_sans_extension():
    """Un fichier sans extension reste inchangé."""
    assert formater_nom_fichier("document") == "document"


def test_formater_fichier_autre_extension():
    """Seule l'extension .md est enlevée."""
    assert formater_nom_fichier("document.txt") == "document.txt"


def test_formater_fichier_vide():
    """Un nom vide reste vide."""
    assert formater_nom_fichier("") == ""


def test_formater_fichier_plusieurs_points():
    """Avec plusieurs points, seul le .md final est enlevé."""
    assert formater_nom_fichier("mon.document.md") == "mon.document"


# ===== TESTS POUR extraire_extension =====

def test_extraire_extension_md():
    """Extrait l'extension md."""
    assert extraire_extension("document.md") == "md"


def test_extraire_extension_txt():
    """Extrait l'extension txt."""
    assert extraire_extension("fichier.txt") == "txt"


def test_extraire_extension_sans():
    """Sans extension, retourne None."""
    assert extraire_extension("fichier") == None


def test_extraire_extension_plusieurs_points():
    """Avec plusieurs points, prend le dernier."""
    assert extraire_extension("mon.fichier.md") == "md"


def test_extraire_extension_vide():
    """Un nom vide retourne None."""
    assert extraire_extension("") == None


def test_extraire_extension_gitignore():
    """Un fichier commençant par un point."""
    assert extraire_extension(".gitignore") == "gitignore"


# ===== TESTS POUR compter_mots =====

def test_compter_mots_simple():
    """Compte les mots d'un texte simple."""
    assert compter_mots("un deux trois") == 3


def test_compter_mots_un_seul():
    """Un seul mot."""
    assert compter_mots("mot") == 1


def test_compter_mots_vide():
    """Un texte vide a zéro mot."""
    assert compter_mots("") == 0


def test_compter_mots_espaces_multiples():
    """Les espaces multiples sont gérés."""
    assert compter_mots("un  deux   trois") == 3


def test_compter_mots_ponctuation():
    """La ponctuation ne compte pas comme mot."""
    assert compter_mots("Bonjour, comment allez-vous?") == 3


def test_compter_mots_sauts_ligne():
    """Les sauts de ligne séparent les mots."""
    assert compter_mots("ligne1\nligne2\nligne3") == 3


def test_compter_mots_none():
    """None donne zéro mots."""
    assert compter_mots(None) == 0


# ===== TESTS POUR tronquer_texte =====

def test_tronquer_texte_court():
    """Un texte court n'est pas tronqué."""
    assert tronquer_texte("Court", 100) == "Court"


def test_tronquer_texte_exactement_limite():
    """Un texte à la limite exacte n'est pas tronqué."""
    texte = "A" * 100
    assert tronquer_texte(texte, 100) == texte


def test_tronquer_texte_long():
    """Un texte trop long est tronqué avec '...'."""
    texte = "A" * 150
    resultat = tronquer_texte(texte, 100)
    # 100 caractères + "..." = 103
    assert len(resultat) == 103
    assert resultat.endswith("...")


def test_tronquer_texte_vide():
    """Un texte vide reste vide."""
    assert tronquer_texte("") == ""


def test_tronquer_texte_suffixe_personnalise():
    """On peut changer le suffixe '...'."""
    texte = "A" * 150
    resultat = tronquer_texte(texte, 100, suffixe=" [suite]")
    assert resultat.endswith(" [suite]")


def test_tronquer_texte_none():
    """None devient une chaîne vide."""
    assert tronquer_texte(None) == ""
