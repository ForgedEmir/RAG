"""
Loads a file and extracts its text via Unstructured.
If Unstructured fails, falls back to the custom parser.
"""
import os
import logging
from typing import List, Optional

from langchain_core.documents import Document
from src.ingestion.parser import clean_text, extract_text_from_file

logger = logging.getLogger(__name__)


def _try_partition(filepath: str) -> list:
    """Lazy import of Unstructured to avoid crashes on startup."""
    from unstructured.partition.auto import partition
    return partition(filepath)


def load_document(filepath: str) -> List[Document]:
    """Reads a file and returns cleaned LangChain Documents.
    Tries Unstructured first, then custom parser as fallback.
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return []

    try:
        elements = _try_partition(filepath)
        if not elements:
            return _fallback_custom(filepath)

        docs = []
        for elem in elements:
            texte = clean_text(elem.text)
            if texte:
                docs.append(Document(page_content=texte, metadata={"source": filepath}))
        return docs

    except Exception as e:
        logger.warning(f"Unstructured failed for {filepath}: {e}. Fallback enabled.")
        return _fallback_custom(filepath)


def _fallback_custom(filepath: str) -> List[Document]:
    """Custom parser in case Unstructured fails."""
    texte = extract_text_from_file(filepath)
    if texte:
        texte = clean_text(texte)
        if texte:
            return [Document(page_content=texte, metadata={"source": filepath})]
    return []


def extract_text_with_unstructured(filepath: str) -> Optional[str]:
    """Extracts all text from a file into a single string."""
    docs = load_document(filepath)
    if not docs:
        return None
    texte = "\n\n".join(doc.page_content for doc in docs)
    return texte if texte.strip() else None
