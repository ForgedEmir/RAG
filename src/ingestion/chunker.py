"""
Module chunker : découpe un long texte en petits morceaux (chunks)
pour que la base de données vectorielle puisse les stocker et les comparer.

Stratégie : on découpe d'abord par paragraphe (double saut de ligne),
puis on regroupe les petits paragraphes ensemble tant qu'on ne dépasse
pas la taille maximale. Cela garantit que chaque chunk traite d'un sujet cohérent.
"""
from typing import List


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Découpe un texte en morceaux intelligents basés sur les paragraphes.

    1. On sépare le texte en paragraphes (séparés par des lignes vides)
    2. Les paragraphes courts sont regroupés jusqu'à +-chunk_size caractères
    3. Les paragraphes trop longs sont découpés en sous-morceaux

    Avantage par rapport au découpage fixe : chaque chunk garde un contexte
    cohérent (un artefact, un personnage, un lieu...) au lieu de couper
    au milieu d'une phrase.
    """
    if not text:
        return []

    # Sécurité : le chevauchement ne peut pas être plus grand que le morceau
    if overlap >= chunk_size:
        overlap = chunk_size // 5

    # Étape 1 : séparer par paragraphe (double saut de ligne)
    paragraphes = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    chunk_actuel = ""

    for paragraphe in paragraphes:
        # Cas 1 : le paragraphe seul est trop long → le découper en sous-morceaux
        if len(paragraphe) > chunk_size:
            # D'abord, sauvegarder ce qu'on a accumulé
            if chunk_actuel.strip():
                chunks.append(chunk_actuel.strip())
                chunk_actuel = ""

            # Découper le gros paragraphe par phrases ou par taille fixe
            pas = chunk_size - overlap
            for i in range(0, len(paragraphe), pas):
                morceau = paragraphe[i:i + chunk_size].strip()
                if morceau:
                    chunks.append(morceau)
            continue

        # Cas 2 : ajouter le paragraphe au chunk actuel s'il rentre
        if len(chunk_actuel) + len(paragraphe) + 2 <= chunk_size:
            if chunk_actuel:
                chunk_actuel += "\n\n" + paragraphe
            else:
                chunk_actuel = paragraphe
        else:
            # Le chunk actuel est plein → on le sauvegarde et on commence un nouveau
            if chunk_actuel.strip():
                chunks.append(chunk_actuel.strip())
            chunk_actuel = paragraphe

    # Ne pas oublier le dernier chunk
    if chunk_actuel.strip():
        chunks.append(chunk_actuel.strip())

    return chunks