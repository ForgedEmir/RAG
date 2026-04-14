"""
Pipeline d'indexation des fichiers de lore.
Détecte les fichiers nouveaux/modifiés/supprimés et met à jour Qdrant.
"""
import hashlib
import json
import logging
import os
import tempfile
import threading
from typing import List, Set

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.vector_store import get_store, add_documents, remove_files
from src.security.validator import check_patterns

logger = logging.getLogger(__name__)

DATA_FOLDER         = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
_DATA_DIR           = os.path.join(os.path.dirname(__file__), "qdrant_db")
MEMORY_FILE         = os.path.join(_DATA_DIR, "files_metadata.json")
BM25_CORPUS_FILE    = os.path.join(_DATA_DIR, "bm25_corpus.json")
SUPPORTED_EXTENSIONS = (".md", ".txt", ".json", ".csv", ".xlsx", ".xml", ".pdf")
PARSER_MODE         = os.getenv("PARSER", "custom")

_CHUNK_CTX_REDIS_TTL = 86400   # 24h — clé "chunk_ctx:{md5_hash}"

# LLM singleton thread-safe
_llm_checker      = None
_llm_checker_lock = threading.Lock()


def _get_llm_checker() -> ChatOpenAI:
    global _llm_checker
    if _llm_checker is not None:
        return _llm_checker
    with _llm_checker_lock:
        if _llm_checker is None:
            _llm_checker = ChatOpenAI(
                model=os.getenv("LLM_MODEL", "deepseek-chat"),
                base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
                api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
                temperature=0,
                max_tokens=10,
            )
    return _llm_checker


# ── Redis (optionnel) ─────────────────────────────────────────────────────────

def _get_redis():
    """Retourne un client Redis ou None si indisponible. Fail-open."""
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
        r.ping()
        return r
    except Exception:
        return None


# ── Mémoire des fichiers indexés ─────────────────────────────────────────────

def load_memory() -> dict:
    """Lit le fichier de suivi des dates de modification."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            logger.warning("Mémoire fichiers invalide (type inattendu), reset.")
        except json.JSONDecodeError as e:
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
            logger.warning(f"Mémoire fichiers JSON corrompue, reset : {e}")
        except Exception as e:
            logger.warning(f"Impossible de lire la mémoire fichiers, reset : {e}")
    return {}


def save_memory(fichiers: dict) -> None:
    dirpath = os.path.dirname(MEMORY_FILE)
    os.makedirs(dirpath, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="files_metadata_", suffix=".json", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(fichiers, f, indent=2)
        os.replace(tmp_path, MEMORY_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def list_current_files() -> dict:
    if not os.path.exists(DATA_FOLDER):
        return {}
    return {
        nom: os.path.getmtime(os.path.join(DATA_FOLDER, nom))
        for nom in os.listdir(DATA_FOLDER)
        if nom.lower().endswith(SUPPORTED_EXTENSIONS)
    }


# ── Validation du contenu ────────────────────────────────────────────────────

def _is_lore_content(texte: str, nom: str) -> bool:
    """Vérifie via LLM que le fichier contient du lore. Fail-open si LLM indisponible."""
    try:
        llm      = _get_llm_checker()
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


# ── Context-Aware Enrichissement ─────────────────────────────────────────────

def _get_doc_context(texte: str, nom: str) -> dict:
    """Génère un résumé et des entités nommées pour enrichir les metadata de chaque chunk.

    WHY: Injecter le contexte global dans chaque chunk améliore la précision RAG
    sur les questions qui font référence à des éléments mentionnés ailleurs dans le document.
    Cache Redis 24h sur le hash MD5 du texte pour éviter les appels LLM redondants.
    """
    content_hash = hashlib.md5(texte[:5000].encode()).hexdigest()
    redis_key    = f"chunk_ctx:{content_hash}"

    # Tentative de récupération depuis Redis
    redis_client = _get_redis()
    if redis_client:
        try:
            cached = redis_client.get(redis_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # Appel LLM
    context = {"doc_summary": "", "entities": []}
    try:
        llm = _get_llm_checker()
        # On réutilise un LLM avec max_tokens plus généreux pour le résumé
        summary_llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            temperature=0,
            max_tokens=200,
        )
        result = summary_llm.invoke([
            SystemMessage(content=(
                "Tu analyses du lore de jeu. Réponds en JSON strict (pas de markdown) avec deux clés : "
                "'summary' (résumé 2-3 phrases), "
                "'entities' (liste de strings : noms de personnages, lieux, factions, artefacts). "
                "Exemple : {\"summary\": \"...\", \"entities\": [\"Aethon\", \"Cité de Vael\"]}"
            )),
            HumanMessage(content=f"Document '{nom}' :\n\n{texte[:3000]}"),
        ])
        raw = result.content.strip()
        # Strip markdown code fences if LLM wraps JSON in ```json ... ```
        if raw.startswith("```"):
            try:
                raw = raw.split("```")[1]
                if raw.startswith("json\n") or raw.startswith("json\r\n"):
                    raw = raw[4:]
            except Exception:
                pass
        brace_start = raw.find("{")
        brace_end = raw.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            raw = raw[brace_start:brace_end+1]
        context = json.loads(raw.strip())
        # LLM returns "summary" key but we store as "doc_summary"
        if "summary" in context and "doc_summary" not in context:
            context["doc_summary"] = context.pop("summary")
        if not isinstance(context.get("entities"), list):
            context["entities"] = []
    except Exception as e:
        logger.warning(f"Contexte doc impossible pour '{nom}' : {e}")

    # Mise en cache Redis
    if redis_client:
        try:
            redis_client.setex(redis_key, _CHUNK_CTX_REDIS_TTL, json.dumps(context))
        except Exception:
            pass

    return context


# ── Pipeline d'indexation ────────────────────────────────────────────────────

def prepare_files_for_ai(noms_fichiers: Set[str]) -> List[Document]:
    """Traite les fichiers et retourne des Documents prêts à indexer.
    Pipeline : extraction → vérif hors-sujet → contexte doc → découpage → filtrage anti-injection
    """
    documents = []

    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
        if not os.path.exists(chemin):
            continue

        try:
            ext = os.path.splitext(nom)[1].lower()
            if PARSER_MODE == "unstructured" and ext != ".json":
                from src.ingestion.document_loader import extract_text_with_unstructured
                texte = extract_text_with_unstructured(chemin)
            else:
                brut  = extract_text_from_file(chemin)
                texte = clean_text(brut) if brut else None

            if not texte:
                continue

            if not _is_lore_content(texte, nom):
                logger.warning(f"'{nom}' ignoré : contenu hors-sujet.")
                continue

            # Contexte global du document (résumé + entités) injecté dans chaque chunk
            doc_context = _get_doc_context(texte, nom)

            for chunk_idx, chunk in enumerate(split_into_chunks(texte)):
                if not check_patterns(chunk)["valid"]:
                    logger.warning(f"Chunk suspect ignoré dans '{nom}'.")
                    continue
                chunk_id = f"{nom}_{chunk_idx}"
                documents.append(Document(
                    page_content=chunk,
                    metadata={
                        "fichier":     nom,
                        "chunk_id":    chunk_id,
                        "doc_summary": doc_context.get("doc_summary", ""),
                        "entities":    doc_context.get("entities", []),
                    },
                ))

        except Exception as e:
            logger.error(f"Erreur sur '{nom}' : {e}")

    return documents


def _save_bm25_corpus(documents: List[Document]) -> None:
    """Sauvegarde les chunks en JSON pour la hybrid search BM25."""
    os.makedirs(os.path.dirname(BM25_CORPUS_FILE), exist_ok=True)
    corpus = [
        {"id": doc.metadata.get("chunk_id", f"doc_{i}"), "text": doc.page_content, "fichier": doc.metadata.get("fichier", "inconnu")}
        for i, doc in enumerate(documents)
    ]
    dirpath = os.path.dirname(BM25_CORPUS_FILE)
    fd, tmp_path = tempfile.mkstemp(prefix="bm25_corpus_", suffix=".json", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(corpus, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, BM25_CORPUS_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    logger.info(f"Corpus BM25 sauvegardé ({len(corpus)} chunks).")

    try:
        from src.search.search import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception as e:
        logger.warning(f"Impossible d'invalider le cache BM25 : {e}")


def index_data(force_reindex: bool = False) -> bool:
    """Met à jour Qdrant avec les fichiers nouveaux/modifiés/supprimés."""
    logger.info("Vérification des fichiers de lore...")
    fichiers_actuels = list_current_files()

    if force_reindex:
        store = get_store(force_reindex=True)
        docs  = prepare_files_for_ai(set(fichiers_actuels.keys()))
        if docs:
            add_documents(store, docs)
            _save_bm25_corpus(docs)
            save_memory(fichiers_actuels)
            logger.info("Réindexation complète terminée.")
        else:
            logger.warning("Collection recréée mais aucun fichier valide trouvé dans data/sample.")
        return True

    memoire  = load_memory()
    actuels  = set(fichiers_actuels.keys())
    anciens  = set(memoire.keys())

    supprimes = anciens - actuels
    nouveaux  = actuels - anciens
    modifies  = {n for n in (actuels & anciens) if fichiers_actuels[n] > memoire[n]}

    if not (supprimes or nouveaux or modifies):
        logger.info("Aucun changement détecté.")
        if not os.path.exists(BM25_CORPUS_FILE):
            logger.info("Corpus BM25 absent — reconstruction depuis les fichiers actuels.")
            all_docs = prepare_files_for_ai(actuels)
            _save_bm25_corpus(all_docs)
        return False

    store = get_store(force_reindex=False)

    if supprimes | modifies:
        remove_files(store, supprimes | modifies)

    a_indexer = nouveaux | modifies
    new_docs = []
    if a_indexer:
        new_docs = prepare_files_for_ai(a_indexer)
        add_documents(store, new_docs)

    # WHY: On reconstruit le corpus BM25 uniquement depuis les fichiers changés +
    # les anciens non modifiés, évitant de tout retraiter.
    unchanged   = actuels - a_indexer - supprimes
    stable_docs = prepare_files_for_ai(unchanged)
    _save_bm25_corpus(new_docs + stable_docs)

    save_memory(fichiers_actuels)
    logger.info(f"Mise à jour : +{len(nouveaux)} nouveau(x), ~{len(modifies)} modifié(s), -{len(supprimes)} supprimé(s).")
    return True


if __name__ == "__main__":
    index_data(force_reindex=False)
