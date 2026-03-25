"""
Découpe un texte long en morceaux (chunks) pour l'indexation.
Respecte paragraphes et phrases pour garder le sens intact.
"""
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# Splitter par défaut, réutilisé partout
_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200, separators=_SEPARATORS)


def split_into_chunks(text: str, chunk_size: int = 1200, overlap: int = 200) -> List[str]:
    """Découpe le texte avec chevauchement pour garder le contexte entre chunks."""
    if not text:
        return []
    if chunk_size == 1200 and overlap == 200:
        return _SPLITTER.split_text(text)
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=min(overlap, chunk_size // 5) if overlap >= chunk_size else overlap,
        separators=_SEPARATORS,
    ).split_text(text)
