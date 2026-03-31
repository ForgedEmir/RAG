"""
Pipeline d'indexation des fichiers de lore.
Détecte les fichiers nouveaux/modifiés/supprimés et met à jour Qdrant.
"""
import os
import json
import logging
from typing import List, Set

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.vector_store import get_store, add_documents, remove_files
from src.security.validator import check_patterns

logger = logging.getLogger(__name__)

DATA_FOLDER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
_DATA_DIR = os.path.join(os.path.dirname(__file__), "qdrant_db")
MEMORY_FILE = os.path.join(_DATA_DIR, "files_metadata.json")
BM25_CORPUS_FILE = os.path.join(_DATA_DIR, "bm25_corpus.json")
SUPPORTED_EXTENSIONS = (".md", ".txt", ".csv", ".xlsx", ".xml", ".pdf")
PARSER_MODE = os.getenv("PARSER", "unstructured")

# LLM pour vérifier si un fichier contient bien du lore (singleton)
_llm_checker = None


def _get_llm_checker() -> ChatOpenAI:
    global _llm_checker
    if _llm_checker is None:
        _llm_checker = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0,
            max_tokens=10,
        )
    return _llm_checker


# ── Mémoire des fichiers indexés ─────────────────────────────────────────────

def load_memory() -> dict:
    """Lit le fichier de suivi des dates de modification."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_memory(fichiers: dict) -> None:
    """Sauvegarde les dates de modification actuelles."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(fichiers, f, indent=2)


def list_current_files() -> dict:
    """Retourne {nom_fichier: date_modification} pour les fichiers supportés."""
    if not os.path.exists(DATA_FOLDER):
        return {}
    return {
        nom: os.path.getmtime(os.path.join(DATA_FOLDER, nom))
        for nom in os.listdir(DATA_FOLDER)
        if nom.lower().endswith(SUPPORTED_EXTENSIONS)
    }


# ── Validation du contenu ────────────────────────────────────────────────────

def _is_lore_content(texte: str, nom: str) -> bool:
    """Vérifie via LLM que le fichier contient du lore et pas du hors-sujet.
    Fail-open si le LLM est indisponible.
    """
    try:
        llm = _get_llm_checker()
        response = llm.invoke([
            SystemMessage(content=(
                "Tu valides du contenu pour une base de lore de jeu de rôle fantastique. "
                "Réponds OUI si le texte contient du lore (personnages, lieux, artefacts, factions, histoire fictive). "
                "Réponds NON si c'est clairement hors-sujet (recette, code, document réel). "
                "En cas de doute, réponds OUI."
            )),
            HumanMessage(content=f"Fichier '{nom}' :\n\n{texte[:2000]}"),
        ])
        return "NON" not in response.content.strip().upper()
    except Exception as e:
        logger.warning(f"Vérification impossible pour '{nom}', accepté par défaut : {e}")
        return True


# ── Pipeline d'indexation ────────────────────────────────────────────────────

def prepare_files_for_ai(noms_fichiers: Set[str]) -> List[Document]:
    """Traite les fichiers et retourne des Documents prêts à indexer.
    Pipeline : extraction → vérif hors-sujet → découpage → filtrage anti-injection
    """
    documents = []

    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
        if not os.path.exists(chemin):
            continue

        try:
            # 1. Extraction du texte
            if PARSER_MODE == "unstructured":
                from src.ingestion.document_loader import extract_text_with_unstructured
                texte = extract_text_with_unstructured(chemin)
            else:
                brut = extract_text_from_file(chemin)
                texte = clean_text(brut) if brut else None

            if not texte:
                continue

            # 2. Vérification hors-sujet
            if not _is_lore_content(texte, nom):
                logger.warning(f"'{nom}' ignoré : contenu hors-sujet.")
                continue

            # 3. Découpage + filtrage des chunks suspects
            for chunk_idx, chunk in enumerate(split_into_chunks(texte)):
                if not check_patterns(chunk)["valid"]:
                    logger.warning(f"Chunk suspect ignoré dans '{nom}'.")
                    continue
                chunk_id = f"{nom}_{chunk_idx}"
                documents.append(Document(page_content=chunk, metadata={"fichier": nom, "chunk_id": chunk_id}))

        except Exception as e:
            logger.error(f"Erreur sur '{nom}' : {e}")

    return documents


def _save_bm25_corpus(documents: List[Document]) -> None:
    """Sauvegarde les chunks en JSON pour que la hybrid search puisse construire BM25."""
    os.makedirs(os.path.dirname(BM25_CORPUS_FILE), exist_ok=True)
    corpus = [
        {"id": doc.metadata.get("chunk_id", f"doc_{i}"), "text": doc.page_content, "fichier": doc.metadata.get("fichier", "inconnu")}
        for i, doc in enumerate(documents)
    ]
    with open(BM25_CORPUS_FILE, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
    logger.info(f"Corpus BM25 sauvegardé ({len(corpus)} chunks).")

    # Invalide le cache en mémoire pour forcer le rechargement au prochain appel
    try:
        from src.search.search import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception as e:
        logger.warning(f"Impossible d'invalider le cache BM25 : {e}")


def index_data(force_reindex: bool = False) -> bool:
    """Met à jour Qdrant avec les fichiers nouveaux/modifiés/supprimés.
    Si force_reindex=True, repart de zéro.
    """
    logger.info("Vérification des fichiers de lore...")
    fichiers_actuels = list_current_files()

    if force_reindex:
        # Supprime et recrée la collection AVANT de préparer les docs
        # (même si le dossier data/sample est vide)
        store = get_store(force_reindex=True)
        docs = prepare_files_for_ai(set(fichiers_actuels.keys()))
        if docs:
            add_documents(store, docs)
            _save_bm25_corpus(docs)
            save_memory(fichiers_actuels)
            logger.info("Réindexation complète terminée.")
        else:
            logger.warning("Collection recréée mais aucun fichier valide trouvé dans data/sample.")
        return True

    # Détection des changements
    memoire = load_memory()
    actuels  = set(fichiers_actuels.keys())
    anciens  = set(memoire.keys())

    supprimes = anciens - actuels
    nouveaux  = actuels - anciens
    modifies  = {n for n in (actuels & anciens) if fichiers_actuels[n] > memoire[n]}

    if not (supprimes or nouveaux or modifies):
        logger.info("Aucun changement détecté.")
        # Reconstruire le corpus BM25 si le fichier est absent (nouveau conteneur)
        if not os.path.exists(BM25_CORPUS_FILE):
            logger.info("Corpus BM25 absent — reconstruction depuis les fichiers actuels.")
            all_docs = prepare_files_for_ai(actuels)
            _save_bm25_corpus(all_docs)
        return False

    store = get_store(force_reindex=False)

    if supprimes | modifies:
        remove_files(store, supprimes | modifies)

    a_indexer = nouveaux | modifies
    if a_indexer:
        docs = prepare_files_for_ai(a_indexer)
        add_documents(store, docs)

    # Reconstruire le corpus BM25 complet (tous les fichiers actuels)
    all_docs = prepare_files_for_ai(actuels)
    _save_bm25_corpus(all_docs)

    save_memory(fichiers_actuels)
    logger.info(f"Mise à jour : +{len(nouveaux)} nouveau(x), ~{len(modifies)} modifié(s), -{len(supprimes)} supprimé(s).")
    return True


if __name__ == "__main__":
    index_data(force_reindex=False)
