from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
_DEFAULT_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP, separators=_SEPARATORS)


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    if chunk_size == CHUNK_SIZE and overlap == CHUNK_OVERLAP:
        return _DEFAULT_SPLITTER.split_text(text)
    # Prevents processing errors by capping overlap at 20% of chunk size
    safe_overlap = min(overlap, chunk_size // 5) if overlap >= chunk_size else overlap
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=safe_overlap, separators=_SEPARATORS).split_text(text)
