"""
Ce module s'occupe de la découpe des textes.
Plutôt que de couper bêtement tous les 1000 caractères au milieu d'une phrase,
il essaie d'être intelligent : il garde les paragraphes entiers ensemble.
Comme ça, l'IA reçoit un bloc de texte qui a du sens du début à la fin.
"""
from typing import List


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Découpe un texte long en plusieurs "morceaux" (chunks).

    La logique :
    1. On coupe d'abord par paragraphe (quand il y a un double saut de ligne).
    2. On recolle les petits paragraphes ensemble jusqu'à atteindre notre limite (chunk_size).
    3. Si un seul paragraphe est gigantesque, on est obligé de le couper.
    """
    if not text:
        return []

    # Petit détail technique : pour que les morceaux ne s'enchaînent pas de façon trop brute,
    # on essaie de garder un petit chevauchement (overlap) si on coupe un gros bloc.
    if overlap >= chunk_size:
        overlap = chunk_size // 5

    # Étape 1 : on isole chaque paragraphe proprement
    paragraphes = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    chunk_actuel = ""

    for paragraphe in paragraphes:
        # Cas 1 : Ce paragraphe à lui seul dépasse notre limite physique !
        if len(paragraphe) > chunk_size:
            # On met de côté ce qu'on avait déjà accumulé dans la boucle précédente
            if chunk_actuel.strip():
                chunks.append(chunk_actuel.strip())
                chunk_actuel = ""

            # On découpe le paragraphe monstre de façon régulière
            pas = chunk_size - overlap
            for i in range(0, len(paragraphe), pas):
                morceau = paragraphe[i:i + chunk_size].strip()
                if morceau:
                    chunks.append(morceau)
            continue

        # Cas 2 : Le paragraphe est normal, est-ce qu'il rentre dans la boîte actuelle ?
        if len(chunk_actuel) + len(paragraphe) + 2 <= chunk_size:
            if chunk_actuel:
                chunk_actuel += "\n\n" + paragraphe
            else:
                chunk_actuel = paragraphe
        else:
            # Et non, la boîte est pleine ! 
            # On la ferme et on en ouvre une nouvelle avec ce paragraphe.
            if chunk_actuel.strip():
                chunks.append(chunk_actuel.strip())
            chunk_actuel = paragraphe

    # Fin de la boucle, on n'oublie pas de glisser la dernière boîte dans le camion avant de partir
    if chunk_actuel.strip():
        chunks.append(chunk_actuel.strip())

    return chunks
