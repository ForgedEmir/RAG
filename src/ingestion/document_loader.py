"""
Charge un fichier et extrait son texte via Unstructured.
Si Unstructured échoue ou retourne du texte vide, bascule sur le parser maison
(qui inclut PyMuPDF comme fallback PDF).
"""
import os
import logging
from typing import List, Optional

from langchain_core.documents import Document
from src.ingestion.parser import clean_text, extract_text_from_file

logger = logging.getLogger(__name__)


def _try_partition(filepath: str) -> list:
    """Import paresseux d'Unstructured pour éviter les crashes au démarrage."""
    from unstructured.partition.auto import partition
    return partition(filepath)


def load_document(filepath: str) -> List[Document]:
    """Lit un fichier et retourne des Documents LangChain nettoyés.
    Essaye Unstructured d'abord, puis le parser custom en fallback.

    Le parser custom (extract_text_from_file) inclut PyMuPDF comme fallback PDF,
    garantissant l'extraction même si Unstructured n'a pas les dépendances système
    (poppler, tesseract, etc.).
    """
    if not os.path.exists(filepath):
        logger.error(f"Fichier introuvable : {filepath}")
        return []

    try:
        elements = _try_partition(filepath)
        if not elements:
            logger.info(f"Unstructured n'a retourné aucun élément pour {filepath}, fallback activé.")
            return _fallback_custom(filepath)

        docs = []
        for elem in elements:
            texte = clean_text(elem.text)
            if texte:
                docs.append(Document(page_content=texte, metadata={"source": filepath}))

        # FIX: Si Unstructured retourne des éléments mais tout le texte est vide
        # après nettoyage, on déclenche quand même le fallback custom (PyMuPDF).
        if not docs:
            logger.info(f"Unstructured a retourné uniquement du texte vide pour {filepath}, fallback activé.")
            return _fallback_custom(filepath)

        return docs

    except Exception as e:
        logger.warning(f"Unstructured a échoué pour {filepath} : {e}. Fallback activé.")
        return _fallback_custom(filepath)


def _fallback_custom(filepath: str) -> List[Document]:
    """Parser maison en cas d'échec d'Unstructured.
    Utilise extract_text_from_file qui inclut PyMuPDF comme fallback PDF."""
    texte = extract_text_from_file(filepath)
    if texte:
        texte = clean_text(texte)
        if texte:
            return [Document(page_content=texte, metadata={"source": filepath})]
    return []


def extract_text_with_unstructured(filepath: str) -> Optional[str]:
    """Extrait tout le texte d'un fichier en une seule chaîne."""
    docs = load_document(filepath)
    if not docs:
        return None
    texte = "\n\n".join(doc.page_content for doc in docs)
    return texte if texte.strip() else None
