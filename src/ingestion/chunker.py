"""
Module chunker : découpe un long texte en petits morceaux (chunks)
pour que la base de données vectorielle puisse les stocker et les comparer.
"""
from typing import List


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Découpe un texte en morceaux de +-1200 caractères avec un chevauchement de 200.
    Le chevauchement permet de ne pas couper une phrase en deux sans contexte.

    Exemple : avec un texte de 3000 caractères, chunk_size=1200, overlap=200
    -> Morceau 1 : caractères 0 à 1200
    -> Morceau 2 : caractères 1000 à 2200  (les 200 derniers du morceau 1 sont repris)
    -> Morceau 3 : caractères 2000 à 3000
    """
    if not text:
        return []

    # Sécurité : le chevauchement ne peut pas être plus grand que le morceau
    if overlap >= chunk_size:
        overlap = chunk_size // 5

    chunks = []

    # On avance de (chunk_size - overlap) à chaque pas
    pas = chunk_size - overlap

    for i in range(0, len(text), pas):
        morceau = text[i:i + chunk_size].strip()
        if morceau:
            chunks.append(morceau)

    return chunks