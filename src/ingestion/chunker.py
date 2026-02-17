from typing import List

def decouper_en_chunks(texte: str, taille: int = 375) -> List[str]:
    mots = texte.split()
    chunks: List[str] = []
    for i in range(0, len(mots), taille):
        chunks.append(" ".join(mots[i:i + taille]))
    return chunks