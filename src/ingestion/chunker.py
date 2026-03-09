"""
Ce module s'occupe de la decoupe des textes en utilisant LangChain.
Le RecursiveCharacterTextSplitter est plus robuste que notre ancien decoupage maison :
il gere mieux les cas limites et respecte les frontieres semantiques (paragraphes, phrases).
"""
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Decoupe un texte long en plusieurs "morceaux" (chunks) via LangChain.

    La logique :
    1. Essaie de couper par paragraphe (double saut de ligne).
    2. Si un paragraphe est trop long, coupe par ligne, puis par phrase, puis par mot.
    3. Garde un chevauchement (overlap) entre les morceaux pour preserver le contexte.
    """
    if not text:
        return []

    # Garde-fou : si l'overlap depasse la taille du chunk, on le reduit
    if overlap >= chunk_size:
        overlap = chunk_size // 5

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    return splitter.split_text(text)
