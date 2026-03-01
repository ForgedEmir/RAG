"""
Tests unitaires pour le module chunker

Ce fichier teste la fonction split_into_chunks qui découpe un texte en morceaux.
"""

# Import de la fonction à tester
from src.ingestion.chunker import split_into_chunks


# Test 1: Texte vide
def test_texte_vide():
    """On teste avec un texte vide, ça devrait donner une liste vide."""
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


# Test 3: Plusieurs paragraphes
def test_plusieurs_paragraphes():
    """On teste avec plusieurs paragraphes."""
    texte = "Premier paragraphe.\n\nDeuxième paragraphe."
    resultat = split_into_chunks(texte, chunk_size=200)
    
    # On vérifie qu'on a au moins un morceau
    assert len(resultat) >= 1
    # On vérifie que les textes sont présents
    assert "Premier" in str(resultat)
    assert "Deuxième" in str(resultat)


# Test 4: Texte très long qui doit être découpé
def test_texte_long():
    """Un texte de 1500 caractères doit être découpé en plusieurs morceaux."""
    # On crée un long texte en répétant "A"
    texte_long = "A" * 1500
    resultat = split_into_chunks(texte_long, chunk_size=500)
    
    # On devrait avoir au moins 2 morceaux
    assert len(resultat) >= 2
    # Chaque morceau doit faire maximum 500 caractères
    for morceau in resultat:
        assert len(morceau) <= 500


# Test 5: Taille personnalisée
def test_taille_personnalisee():
    """On peut choisir la taille des morceaux."""
    texte = "X" * 100
    resultat = split_into_chunks(texte, chunk_size=50)
    
    # Avec 100 caractères et des morceaux de 50, on a au moins 2 morceaux
    assert len(resultat) >= 2
    # Chaque morceau fait maximum 50 caractères
    for morceau in resultat:
        assert len(morceau) <= 50


# Test 6: Overlap (chevauchement)
def test_overlap():
    """L'overlap permet de garder du contexte entre les morceaux."""
    texte = "A" * 300
    resultat = split_into_chunks(texte, chunk_size=150, overlap=50)
    
    # On devrait avoir au moins 2 morceaux
    assert len(resultat) >= 2


# Test 7: Type de retour
def test_type_retour():
    """Le résultat doit être une liste de textes."""
    texte = "Test"
    resultat = split_into_chunks(texte)
    
    # On vérifie que c'est bien une liste
    assert type(resultat) == list
    # On vérifie que les éléments sont des textes
    for morceau in resultat:
        assert type(morceau) == str


# Test 8: Texte avec caractères spéciaux
def test_caracteres_speciaux():
    """Les accents et caractères spéciaux doivent être gardés."""
    texte = "café élève où"
    resultat = split_into_chunks(texte, chunk_size=200)
    
    assert len(resultat) >= 1
    assert "café" in resultat[0]
