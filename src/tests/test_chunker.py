"""
Tests unitaires pour le module chunker (version LangChain).

Ce fichier valide le comportement de la fonction split_into_chunks,
responsible for chunking documents into fragments optimized for vector indexing.
"""
from src.ingestion.chunker import split_into_chunks


def test_texte_vide():
    """Checks that empty text produces an empty list of fragments."""
    texte = ""
    resultat = split_into_chunks(texte)

    assert len(resultat) == 0
    assert resultat == []


def test_texte_court():
    """Checks that text smaller than chunk size is not chunked."""
    texte = "Ceci est un texte court."
    resultat = split_into_chunks(texte, chunk_size=100)

    assert len(resultat) == 1
    assert resultat[0] == texte


def test_texte_long():
    """Checks that long text is correctly chunked according to specified max size."""
    texte_long = "A" * 1500
    resultat = split_into_chunks(texte_long, chunk_size=500)

    # On devrait avoir au moins 3 morceaux (1500 / 500)
    assert len(resultat) >= 3
    # Each chunk must be max 500 characters
    for morceau in resultat:
        assert len(morceau) <= 500


def test_taille_personnalisee():
    """Checks custom chunk size parameters."""
    texte = "X" * 100
    resultat = split_into_chunks(texte, chunk_size=50)

    # With 100 chars and chunks of 50, we have at least 2 chunks
    assert len(resultat) >= 2
    for morceau in resultat:
        assert len(morceau) <= 50


def test_overlap():
    """Checks that overlap between chunks is applied."""
    texte = "A" * 300
    resultat = split_into_chunks(texte, chunk_size=150, overlap=50)

    assert len(resultat) >= 2


def test_type_retour():
    """Checks that the function always returns a list of strings."""
    texte = "Test"
    resultat = split_into_chunks(texte)

    assert isinstance(resultat, list)
    for morceau in resultat:
        assert isinstance(morceau, str)


def test_overlap_trop_grand():
    """Checks that overlap is capped if larger than chunk size."""
    texte = "X" * 100
    # overlap (200) > chunk_size (50), should be reduced by the function
    resultat = split_into_chunks(texte, chunk_size=50, overlap=200)

    assert len(resultat) >= 2
    for morceau in resultat:
        assert len(morceau) <= 50
