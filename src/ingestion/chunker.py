"""
Découpe un texte long en morceaux (chunks) pour l'indexation.
Respecte les paragraphes et phrases pour garder le sens intact.
"""
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# Splitter par défaut — réutilisé sur tous les fichiers lors de l'indexation
_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200, separators=_SEPARATORS)


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """
    Découpe un texte en morceaux avec chevauchement pour ne pas perdre le contexte entre deux chunks.
    Ordre de découpe : paragraphes → lignes → phrases → mots.
    """
    if not text:
        return []
    if chunk_size == 1200 and overlap == 200:
        return _SPLITTER.split_text(text)
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=min(overlap, chunk_size // 5) if overlap >= chunk_size else overlap,
        separators=_SEPARATORS,
    ).split_text(text)
