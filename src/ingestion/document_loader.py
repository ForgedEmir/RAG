"""
Chargeur de documents via LangChain.
Utilise des loaders specifiques par type de fichier pour une extraction fiable.
Le nettoyage specifique au jeu (%PLAYER_NAME%, balises HTML, etc.)
est applique apres l'extraction via clean_text() du parser maison.

Fallback : si le loader LangChain echoue, on utilise le parser custom.
"""
import os
import logging
from typing import List, Optional
from langchain_core.documents import Document
from src.ingestion.parser import clean_text, extract_text_from_file

logger = logging.getLogger(__name__)


def _get_loader(filepath: str):
    """Retourne le bon loader LangChain selon l'extension du fichier."""
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext in ('.md', '.txt'):
        from langchain_community.document_loaders import TextLoader
        return TextLoader(filepath, encoding='utf-8')

    elif ext == '.csv':
        from langchain_community.document_loaders import CSVLoader
        return CSVLoader(filepath, encoding='utf-8')

    elif ext == '.json':
        from langchain_community.document_loaders import JSONLoader
        return JSONLoader(filepath, jq_schema='.', text_content=False)

    # Pour XML et autres formats, pas de loader LangChain fiable -> fallback custom
    return None


def load_document(filepath: str) -> List[Document]:
    """
    Charge un fichier et retourne une liste de Documents LangChain.
    Utilise un loader LangChain specifique, avec fallback vers le parser custom.
    """
    if not os.path.exists(filepath):
        logger.error(f"Le fichier {filepath} n'existe pas.")
        return []

    try:
        loader = _get_loader(filepath)

        if loader:
            docs = loader.load()
        else:
            # Fallback : parser custom pour les formats sans loader LangChain (XML, XLSX, etc.)
            texte = extract_text_from_file(filepath)
            if not texte:
                return []
            docs = [Document(page_content=texte, metadata={"source": filepath})]

        # Appliquer le nettoyage specifique au jeu sur chaque document
        cleaned_docs = []
        for doc in docs:
            texte_nettoye = clean_text(doc.page_content)
            if texte_nettoye:
                cleaned_docs.append(Document(
                    page_content=texte_nettoye,
                    metadata=doc.metadata
                ))

        return cleaned_docs

    except Exception as e:
        logger.warning(f"Loader LangChain echoue pour {filepath}: {e}. Fallback vers parser custom.")
        # Fallback : parser custom
        texte = extract_text_from_file(filepath)
        if texte:
            texte_nettoye = clean_text(texte)
            if texte_nettoye:
                return [Document(page_content=texte_nettoye, metadata={"source": filepath})]
        return []


def extract_text_with_unstructured(filepath: str) -> Optional[str]:
    """
    Extrait le texte d'un fichier via LangChain loaders et applique clean_text().
    Interface compatible avec l'ancien extract_text_from_file() du parser maison.

    Retourne le texte nettoye, ou None en cas d'erreur.
    """
    docs = load_document(filepath)
    if not docs:
        return None

    # On concatene tous les morceaux en un seul texte
    texte_complet = "\n\n".join(doc.page_content for doc in docs)
    return texte_complet if texte_complet.strip() else None
