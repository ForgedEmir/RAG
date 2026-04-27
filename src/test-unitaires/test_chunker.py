"""
Tests unitaires pour le module chunker (version LangChain).

Ce fichier valide le comportement de la fonction split_into_chunks,
chargée de découper les documents en fragments optimisés pour l'indexation vectorielle.
"""
from src.ingestion.chunker import split_into_chunks


def test_texte_vide():
    """Vérifie qu'un texte vide produit une liste de fragments vide."""
    texte = ""
    resultat = split_into_chunks(texte)

    assert len(resultat) == 0
    assert resultat == []


def test_texte_court():
    """Vérifie qu'un texte plus petit que la taille du fragment n'est pas découpé."""
    texte = "Ceci est un texte court."
    resultat = split_into_chunks(texte, chunk_size=100)

    assert len(resultat) == 1
    assert resultat[0] == texte


def test_texte_long():
    """Vérifie qu'un texte long est correctement fragmenté selon la taille maximale spécifiée."""
    texte_long = "A" * 1500
    resultat = split_into_chunks(texte_long, chunk_size=500)

    # On devrait avoir au moins 3 morceaux (1500 / 500)
    assert len(resultat) >= 3
    # Chaque morceau doit faire maximum 500 caractères
    for morceau in resultat:
        assert len(morceau) <= 500


def test_taille_personnalisee():
    """Vérifie la prise en compte de paramètres de taille de fragment personnalisés."""
    texte = "X" * 100
    resultat = split_into_chunks(texte, chunk_size=50)

    # Avec 100 caractères et des morceaux de 50, on a au moins 2 morceaux
    assert len(resultat) >= 2
    for morceau in resultat:
        assert len(morceau) <= 50


def test_overlap():
    """Vérifie que le chevauchement (overlap) entre les fragments est bien appliqué."""
    texte = "A" * 300
    resultat = split_into_chunks(texte, chunk_size=150, overlap=50)

    assert len(resultat) >= 2


def test_type_retour():
    """Vérifie que la fonction retourne toujours une liste de chaînes de caractères."""
    texte = "Test"
    resultat = split_into_chunks(texte)

    assert isinstance(resultat, list)
    for morceau in resultat:
        assert isinstance(morceau, str)


def test_overlap_trop_grand():
    """Vérifie que l'overlap est automatiquement plafonné s'il est plus grand que la taille du fragment."""
    texte = "X" * 100
    # overlap (200) > chunk_size (50), devrait être réduit automatiquement par la fonction
    resultat = split_into_chunks(texte, chunk_size=50, overlap=200)

    assert len(resultat) >= 2
    for morceau in resultat:
        assert len(morceau) <= 50
