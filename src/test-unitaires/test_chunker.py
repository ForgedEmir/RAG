"""
Tests unitaires pour le module chunker (version LangChain)

Ce fichier teste la fonction split_into_chunks qui decoupe un texte en morceaux
en utilisant RecursiveCharacterTextSplitter de LangChain.
"""
from src.ingestion.chunker import split_into_chunks


# Test 1: Texte vide
def test_texte_vide():
    """On teste avec un texte vide, ca devrait donner une liste vide."""
    texte = ""
    resultat = split_into_chunks(texte)

    assert len(resultat) == 0
    assert resultat == []


# Test 2: Texte court
def test_texte_court():
    """Un texte court devrait tenir dans un seul morceau."""
    texte = "Ceci est un texte court."
    resultat = split_into_chunks(texte, chunk_size=100)

    assert len(resultat) == 1
    assert resultat[0] == texte


# Test 3: Texte tres long qui doit etre decoupe
def test_texte_long():
    """Un texte de 1500 caracteres doit etre decoupe en plusieurs morceaux."""
    texte_long = "A" * 1500
    resultat = split_into_chunks(texte_long, chunk_size=500)

    # On devrait avoir au moins 2 morceaux
    assert len(resultat) >= 2
    # Chaque morceau doit faire maximum 500 caracteres
    for morceau in resultat:
        assert len(morceau) <= 500


# Test 4: Taille personnalisee
def test_taille_personnalisee():
    """On peut choisir la taille des morceaux."""
    texte = "X" * 100
    resultat = split_into_chunks(texte, chunk_size=50)

    # Avec 100 caracteres et des morceaux de 50, on a au moins 2 morceaux
    assert len(resultat) >= 2
    # Chaque morceau fait maximum 50 caracteres
    for morceau in resultat:
        assert len(morceau) <= 50


# Test 5: Overlap (chevauchement)
def test_overlap():
    """L'overlap permet de garder du contexte entre les morceaux."""
    texte = "A" * 300
    resultat = split_into_chunks(texte, chunk_size=150, overlap=50)

    # On devrait avoir au moins 2 morceaux
    assert len(resultat) >= 2


# Test 6: Type de retour
def test_type_retour():
    """Le resultat doit etre une liste de textes."""
    texte = "Test"
    resultat = split_into_chunks(texte)

    assert type(resultat) == list
    for morceau in resultat:
        assert type(morceau) == str


# Test 7: Overlap trop grand
def test_overlap_trop_grand():
    """Si l'overlap depasse chunk_size, il est reduit automatiquement."""
    texte = "X" * 100
    # overlap (200) > chunk_size (50), devrait etre reduit a 10 (50//5)
    resultat = split_into_chunks(texte, chunk_size=50, overlap=200)

    assert len(resultat) >= 2
    for morceau in resultat:
        assert len(morceau) <= 50
