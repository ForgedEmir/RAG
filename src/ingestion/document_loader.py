"""
Chargeur de documents via Unstructured.io.
Utilise la fonction partition() d'Unstructured pour extraire le texte
de n'importe quel format de fichier (Markdown, JSON, CSV, XML, XLSX, etc.)

Le nettoyage specifique au jeu (%PLAYER_NAME%, balises HTML, etc.)
est applique apres l'extraction via clean_text() du parser maison.

Fallback : si Unstructured echoue ou n'est pas installe, on utilise le parser custom.

Note technique : l'import d'Unstructured est fait a l'interieur de la fonction
(import paresseux) car la librairie python-magic peut crasher sur Windows.
"""
import os
import logging
from typing import List, Optional
from langchain_core.documents import Document
from src.ingestion.parser import clean_text, extract_text_from_file

logger = logging.getLogger(__name__)


def _try_partition(filepath: str) -> list:
    """
    Tente d'utiliser Unstructured pour extraire les elements du fichier.
    Import paresseux pour eviter les crashes au demarrage sur Windows
    (python-magic peut provoquer un segfault a l'import).

    Retourne la liste des elements, ou leve une exception si ca echoue.
    """
    from unstructured.partition.auto import partition
    return partition(filepath)


def load_document(filepath: str) -> List[Document]:
    """
    Charge un fichier et retourne une liste de Documents LangChain.
    Utilise Unstructured.io pour l'extraction, avec fallback vers le parser custom.
    """
    if not os.path.exists(filepath):
        logger.error(f"Le fichier {filepath} n'existe pas.")
        return []

    try:
        elements = _try_partition(filepath)

        if not elements:
            logger.warning(f"Unstructured n'a rien extrait de {filepath}. Fallback vers parser custom.")
            return _fallback_custom(filepath)

        # On convertit les Elements Unstructured en Documents LangChain
        # Chaque element a un attribut .text qui contient le texte extrait
        cleaned_docs = []
        for elem in elements:
            texte_nettoye = clean_text(elem.text)
            if texte_nettoye:
                cleaned_docs.append(Document(
                    page_content=texte_nettoye,
                    metadata={"source": filepath}
                ))

        return cleaned_docs

    except Exception as e:
        logger.warning(f"Unstructured a echoue pour {filepath}: {e}. Fallback vers parser custom.")
        return _fallback_custom(filepath)


def _fallback_custom(filepath: str) -> List[Document]:
    """
    Plan B : si Unstructured n'arrive pas a lire le fichier,
    on utilise notre parser maison qui sait gerer les cas tordus.
    """
    texte = extract_text_from_file(filepath)
    if texte:
        texte_nettoye = clean_text(texte)
        if texte_nettoye:
            return [Document(page_content=texte_nettoye, metadata={"source": filepath})]
    return []


def extract_text_with_unstructured(filepath: str) -> Optional[str]:
    """
    Extrait le texte d'un fichier via Unstructured.io et applique clean_text().
    Interface compatible avec l'ancien extract_text_from_file() du parser maison.

    Retourne le texte nettoye, ou None en cas d'erreur.
    """
    docs = load_document(filepath)
    if not docs:
        return None

    # On concatene tous les morceaux en un seul texte
    texte_complet = "\n\n".join(doc.page_content for doc in docs)
    return texte_complet if texte_complet.strip() else None
