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
import time
from typing import Dict, List, Set

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.config.features import env_bool
from src.ingestion.chunker import split_into_chunks
from src.ingestion.parser import extract_text_from_file, clean_text
from src.ingestion.vector_store import get_store, add_documents, remove_files
from src.security.validator import check_patterns

logger = logging.getLogger(__name__)

DATA_FOLDER         = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
_DATA_DIR           = os.path.join(os.path.dirname(__file__), "qdrant_db")
MEMORY_FILE         = os.path.join(_DATA_DIR, "files_metadata.json")
BM25_CORPUS_FILE    = os.path.join(_DATA_DIR, "bm25_corpus.json")
SUPPORTED_EXTENSIONS = (".md", ".txt", ".json", ".csv", ".xlsx", ".xml", ".pdf", ".docx", ".doc")
PARSER_MODE         = os.getenv("PARSER", "custom")
_INGESTION_LORE_CLASSIFIER_ENABLED = env_bool("INGESTION_LORE_CLASSIFIER_ENABLED", True)
_INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED = env_bool("INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED", True)
_CHUNK_DEDUP_ENABLED = env_bool("CHUNK_DEDUP_ENABLED", True)
_LATE_CHUNKING_ENABLED = env_bool("LATE_CHUNKING_ENABLED", True)
_LATE_CHUNKING_WINDOW = max(1, int(os.getenv("LATE_CHUNKING_WINDOW", "3")))

_CHUNK_CTX_REDIS_TTL = 86400   # 24h — clé "chunk_ctx:{md5_hash}"

# LLM singletons thread-safe
# _llm_checker    : max_tokens=10  — classifies lore vs non-lore (OUI/NON)
# _llm_summarizer : max_tokens=200 — generates doc summary + entities
_llm_checker      = None
_llm_checker_lock = threading.Lock()
_llm_summarizer      = None
_llm_summarizer_lock = threading.Lock()

_LLM_COMMON = dict(
    model    = os.getenv("LLM_MODEL",    "deepseek-chat"),
    base_url = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
    api_key  = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"),
    temperature = 0,
)


def _get_llm_checker() -> ChatOpenAI:
    global _llm_checker
    if _llm_checker is not None:
        return _llm_checker
    with _llm_checker_lock:
        if _llm_checker is None:
            _llm_checker = ChatOpenAI(**_LLM_COMMON, max_tokens=10)
    return _llm_checker


def _get_llm_summarizer() -> ChatOpenAI:
    global _llm_summarizer
    if _llm_summarizer is not None:
        return _llm_summarizer
    with _llm_summarizer_lock:
        if _llm_summarizer is None:
            _llm_summarizer = ChatOpenAI(**_LLM_COMMON, max_tokens=400)
    return _llm_summarizer


# ── Redis (optionnel) ─────────────────────────────────────────────────────────

_redis_client      = None
_redis_client_lock = threading.Lock()

def _get_redis():
    """Retourne un client Redis singleton ou None si indisponible. Fail-open."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    with _redis_client_lock:
        if _redis_client is None:
            try:
                import redis
                r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)
                r.ping()
                _redis_client = r
            except Exception:
                pass
    return _redis_client


# ── Mémoire des fichiers indexés ─────────────────────────────────────────────

def _normalize_memory_entry(nom: str, raw) -> dict:
    """Normalise une entrée de mémoire vers le format {mtime, indexed_at}.

    Accepte l'ancien format (raw = float mtime) pour compat ascendante :
    on hydrate indexed_at = mtime pour les fichiers déjà connus, quitte à
    perdre la "vraie" date d'ajout (on n'a pas mieux comme approx).
    """
    if isinstance(raw, dict):
        mtime      = float(raw.get("mtime", 0.0) or 0.0)
        indexed_at = float(raw.get("indexed_at", mtime) or mtime)
        return {"mtime": mtime, "indexed_at": indexed_at}
    # Ancien format : raw est un float (mtime)
    try:
        mtime = float(raw)
    except (TypeError, ValueError):
        logger.warning(f"Entrée mémoire invalide pour {nom}, ignorée.")
        return {"mtime": 0.0, "indexed_at": 0.0}
    return {"mtime": mtime, "indexed_at": mtime}


def load_memory() -> Dict[str, dict]:
    """Lit le fichier de suivi des fichiers indexés.

    Retourne {nom: {mtime, indexed_at}}. Migre silencieusement l'ancien format
    {nom: mtime_float} vers le nouveau.
    """
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {nom: _normalize_memory_entry(nom, raw) for nom, raw in data.items()}
            logger.warning("Mémoire fichiers invalide (type inattendu), reset.")
        except json.JSONDecodeError as e:
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {nom: _normalize_memory_entry(nom, raw) for nom, raw in data.items()}
            except Exception:
                pass
            logger.warning(f"Mémoire fichiers JSON corrompue, reset : {e}")
        except Exception as e:
            logger.warning(f"Impossible de lire la mémoire fichiers, reset : {e}")
    return {}


def save_memory(fichiers: dict) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(fichiers, f, indent=2)


def list_current_files() -> dict:
    if not os.path.exists(DATA_FOLDER):
        return {}
    files = {}
    for root, _, filenames in os.walk(DATA_FOLDER):
        for nom in filenames:
            if nom.lower().endswith(SUPPORTED_EXTENSIONS):
                # On stocke le chemin relatif par rapport à DATA_FOLDER comme clé
                rel_path = os.path.relpath(os.path.join(root, nom), DATA_FOLDER)
                files[rel_path] = os.path.getmtime(os.path.join(root, nom))
    return files


# ── Validation du contenu ────────────────────────────────────────────────────

def _is_lore_content(texte: str, nom: str) -> bool:
    """Vérifie via LLM que le fichier contient du lore. Fail-open si LLM indisponible."""
    if not _INGESTION_LORE_CLASSIFIER_ENABLED:
        return True
    try:
        llm      = _get_llm_checker()
        response = llm.invoke([
            SystemMessage(content=(
                "Tu valides du contenu pour une base de connaissances professionnelle. "
                "Réponds OUI si le texte contient des informations factuelles, techniques, structurelles ou documentaires utiles. "
                "Réponds NON si c've du contenu purement promotionnel, vide, ou sans valeur informationnelle. "
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
    if not _INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED:
        return {"doc_summary": "", "entities": []}

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
        result = _get_llm_summarizer().invoke([
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

def _apply_late_chunking(chunks: List[str]) -> List[str]:
    """Préfixe chaque chunk avec ses voisins précédents pour contextualiser l'embedding.

    WHY: Un chunk embarqué seul perd le contexte du document. En préfixant les
    _LATE_CHUNKING_WINDOW chunks précédents, le vecteur capture la continuité narrative —
    améliore la précision sémantique sur les questions qui font référence à des éléments
    mentionnés plus tôt dans le document.
    Note: page_content stocke le texte original pour la génération ; le texte contextuel
    n'est utilisé qu'au moment de l'embedding (via add_documents → embedder).
    """
    if not _LATE_CHUNKING_ENABLED or len(chunks) <= 1:
        return chunks
    contextual = []
    for i, chunk in enumerate(chunks):
        start = max(0, i - _LATE_CHUNKING_WINDOW)
        context_parts = chunks[start:i]
        if context_parts:
            context = " ".join(context_parts)
            contextual.append(f"Context: {context}\n\nChunk: {chunk}")
        else:
            contextual.append(chunk)
    return contextual


def prepare_files_for_ai(
    noms_fichiers: Set[str],
    indexed_at_map: Dict[str, float] = None,
    tenant_id: str = "",
    data_folder: str = None,
) -> List[Document]:
    """Traite les fichiers et retourne des Documents prêts à indexer.

    indexed_at_map : {nom: timestamp} — date d'ajout originale d'un fichier déjà
    connu. Si absent (nouveau fichier), on génère time.time(). Cette date est
    préservée au re-indexing pour que "fichier modifié" ne redevienne pas
    "fichier nouveau" du point de vue résolution de conflit.
    tenant_id : identifiant du tenant, injecté dans chaque chunk pour l'isolation Qdrant.
    data_folder : dossier source (défaut : DATA_FOLDER global).

    Pipeline : extraction → vérif hors-sujet → contexte doc → découpage → late chunking → filtrage
    """
    documents = []
    seen_chunk_hashes: Set[str] = set()
    dedup_skipped = 0
    indexed_at_map = indexed_at_map or {}
    now = time.time()
    folder = data_folder or DATA_FOLDER

    for nom in noms_fichiers:
        chemin = os.path.join(folder, nom)
        if not os.path.exists(chemin):
            continue
        indexed_at = float(indexed_at_map.get(nom, now))

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

            raw_chunks = split_into_chunks(texte)
            # Late chunking : enrichit chaque chunk avec ses voisins pour l'embedding
            contextual_chunks = _apply_late_chunking(raw_chunks)

            for chunk_idx, (chunk, contextual_chunk) in enumerate(zip(raw_chunks, contextual_chunks)):
                if not check_patterns(chunk)["valid"]:
                    logger.warning(f"Chunk suspect ignoré dans '{nom}'.")
                    continue
                # SHA256 sur le chunk original (pas contextuel) pour une dedup stable
                normalized_chunk = " ".join(chunk.split()).strip().lower()
                chunk_sha256 = hashlib.sha256(normalized_chunk.encode("utf-8")).hexdigest()
                if _CHUNK_DEDUP_ENABLED and chunk_sha256 in seen_chunk_hashes:
                    dedup_skipped += 1
                    continue
                seen_chunk_hashes.add(chunk_sha256)
                chunk_id = f"{nom}_{chunk_idx}"
                documents.append(Document(
                    # page_content = texte contextuel → vecteur capte le contexte voisin
                    # Le texte original est conservé dans metadata pour la génération
                    page_content=contextual_chunk,
                    metadata={
                        "fichier":        nom,
                        "chunk_id":       chunk_id,
                        "chunk_sha256":   chunk_sha256,
                        "original_text":  chunk,
                        "doc_summary":    doc_context.get("doc_summary", ""),
                        "entities":       doc_context.get("entities", []),
                        "indexed_at":     indexed_at,
                        "tenant_id":      tenant_id,
                    },
                ))

        except Exception as e:
            logger.error(f"Erreur sur '{nom}' : {e}")

    if dedup_skipped:
        logger.info(f"Dedup chunks: {dedup_skipped} doublon(s) ignoré(s).")
    if _LATE_CHUNKING_ENABLED:
        logger.info(f"Late chunking actif (window={_LATE_CHUNKING_WINDOW}).")
    return documents


def _save_bm25_corpus(documents: List[Document]) -> None:
    """Sauvegarde les chunks en JSON pour la hybrid search BM25."""
    os.makedirs(os.path.dirname(BM25_CORPUS_FILE), exist_ok=True)
    corpus = []
    for i, doc in enumerate(documents):
        raw_text = doc.metadata.get("original_text") if isinstance(doc.metadata, dict) else None
        bm25_text = raw_text if isinstance(raw_text, str) and raw_text.strip() else doc.page_content
        corpus.append({
            "id": doc.metadata.get("chunk_id", f"doc_{i}"),
            "text": bm25_text,
            "fichier": doc.metadata.get("fichier", "inconnu"),
            "indexed_at": float(doc.metadata.get("indexed_at", 0.0) or 0.0),
        })
    dirpath = os.path.dirname(BM25_CORPUS_FILE)
    fd, tmp_path = tempfile.mkstemp(prefix="bm25_corpus_", suffix=".json", dir=dirpath)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(corpus, f, ensure_ascii=False, indent=1)
        os.replace(tmp_path, BM25_CORPUS_FILE)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    logger.info(f"Corpus BM25 sauvegardé ({len(corpus)} chunks).")

    try:
        from src.search.search import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception as e:
        logger.warning(f"Impossible d'invalider le cache BM25 : {e}")


def bootstrap_bm25_from_qdrant(output_path: str) -> bool:
    """Reconstruit le corpus BM25 en scrollant tous les points Qdrant.

    Appelé quand le fichier corpus est absent mais Qdrant a des données.
    Returns True si le corpus a pu être écrit, False sinon.
    """
    try:
        from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
        client = _get_client()
        corpus = []
        offset = None
        while True:
            results, offset = client.scroll(
                collection_name=_COLLECTION_NAME,
                offset=offset,
                limit=256,
                with_payload=True,
                with_vectors=False,
            )
            for point in results:
                payload = point.payload or {}
                metadata = payload.get("metadata", {})
                text = metadata.get("original_text") or payload.get("page_content", "")
                if not isinstance(text, str) or not text.strip():
                    continue
                corpus.append({
                    "id":         metadata.get("chunk_id", str(point.id)),
                    "text":       text,
                    "fichier":    metadata.get("fichier", "inconnu"),
                    "indexed_at": float(metadata.get("indexed_at", 0.0) or 0.0),
                })
            if offset is None:
                break
        if not corpus:
            return False
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        dirpath = os.path.dirname(output_path)
        fd, tmp_path = tempfile.mkstemp(prefix="bm25_corpus_", suffix=".json", dir=dirpath)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(corpus, f, ensure_ascii=False, indent=1)
            os.replace(tmp_path, output_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        logger.info("Corpus BM25 reconstruit depuis Qdrant (%d chunks).", len(corpus))
        return True
    except Exception as e:
        logger.warning("Bootstrap BM25 depuis Qdrant impossible : %s", e)
        return False


def _is_bm25_corpus_healthy(expected_files: Set[str]) -> bool:
    """Valide rapidement le corpus BM25 persistant.

    WHY: Les tests peuvent laisser un corpus factice (ex: file1.md / Chunk),
    ce qui dégrade la recherche au runtime si aucun changement de fichier n'est détecté.
    """
    if not os.path.exists(BM25_CORPUS_FILE):
        return False

    try:
        with open(BM25_CORPUS_FILE, "r", encoding="utf-8-sig") as f:
            corpus = json.load(f)
    except Exception:
        return False

    if not isinstance(corpus, list) or not corpus:
        return False

    corpus_files = set()
    for entry in corpus:
        if not isinstance(entry, dict):
            return False
        text = entry.get("text")
        fichier = entry.get("fichier")
        if not isinstance(text, str) or not text.strip():
            return False
        if isinstance(fichier, str) and fichier.strip():
            corpus_files.add(fichier)

    # Cas typique de corpus de test: aucun fichier réel du dataset courant.
    if expected_files and not (corpus_files & expected_files):
        return False

    return True


def _build_new_memory(fichiers_actuels: Dict[str, float], memoire: Dict[str, dict]) -> Dict[str, dict]:
    """Construit la nouvelle mémoire en préservant indexed_at pour les fichiers
    déjà connus. Un nouveau fichier reçoit indexed_at = now.
    """
    now = time.time()
    result: Dict[str, dict] = {}
    for nom, mtime in fichiers_actuels.items():
        existing    = memoire.get(nom) or {}
        indexed_at  = float(existing.get("indexed_at", now) or now)
        result[nom] = {"mtime": float(mtime), "indexed_at": indexed_at}
    return result


def _indexed_at_map(memoire: Dict[str, dict]) -> Dict[str, float]:
    return {nom: float(entry.get("indexed_at", 0.0) or 0.0) for nom, entry in memoire.items()}


def _run_async(coro):
    """Helper pour lancer de l'async depuis du code sync."""
    import asyncio
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Déjà dans une boucle d'événements (rare pour index_data mais possible via tests)
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # On ne peut pas facilement attendre ici sans bloquer, 
            # mais index_data est généralement lancé en thread.
            return asyncio.ensure_future(coro, loop=loop)
        else:
            return loop.run_until_complete(coro)


def index_data(force_reindex: bool = False, tenant_id: str = "") -> bool:
    """Met à jour Qdrant avec les fichiers nouveaux/modifiés/supprimés.

    tenant_id : si fourni, les chunks sont tagués et les recherches/suppressions
    sont isolées à ce tenant. Laisser vide pour l'indexation globale (admin).
    """
    logger.info("Vérification des fichiers à indexer (tenant=%s)...", tenant_id or "global")
    fichiers_actuels = list_current_files()

    if force_reindex:
        # WHY: force_reindex repart de zéro — les indexed_at existants n'ont plus
        # de sens (collection vidée), chaque fichier devient "nouveau" avec now.
        new_memory = _build_new_memory(fichiers_actuels, {})
        store = get_store(force_reindex=True)
        docs  = prepare_files_for_ai(set(fichiers_actuels.keys()), _indexed_at_map(new_memory), tenant_id=tenant_id)
        if docs:
            add_documents(store, docs)
            _save_bm25_corpus(docs)
            save_memory(new_memory)
            logger.info("Réindexation complète terminée (tenant=%s).", tenant_id or "global")
        else:
            logger.warning("Collection recréée mais aucun fichier valide trouvé dans data/sample.")
        try:
            from src.caching.semantic_cache import clear_all as _clear_semantic_cache
            # _clear_semantic_cache est asynchrone
            _run_async(_clear_semantic_cache())
            logger.info("Semantic cache vidé (force_reindex).")
        except Exception as e:
            logger.warning(f"Impossible de vider le semantic cache : {e}")
        return True

    memoire  = load_memory()
    actuels  = set(fichiers_actuels.keys())
    anciens  = set(memoire.keys())

    supprimes = anciens - actuels
    nouveaux  = actuels - anciens
    modifies  = {n for n in (actuels & anciens) if fichiers_actuels[n] > float(memoire[n].get("mtime", 0.0) or 0.0)}

    if not (supprimes or nouveaux or modifies):
        logger.info("Aucun changement détecté.")
        # Qdrant peut être vide (restart, reset) même si la mémoire dit "tout indexé"
        try:
            _store = get_store(force_reindex=False)
            _info = _store.client.get_collection(_store.collection_name)
            if (_info.points_count or 0) == 0 and actuels:
                logger.warning("Qdrant vide mais mémoire non vide — réindexation forcée.")
                return index_data(force_reindex=True, tenant_id=tenant_id)
        except Exception as e:
            logger.warning(f"Impossible de vérifier l'état Qdrant : {e}")
        if not _is_bm25_corpus_healthy(actuels):
            logger.info("Corpus BM25 absent/invalide — tentative de reconstruction légère depuis Qdrant.")
            try:
                from src.search.search import _load_bm25
                _load_bm25()
            except Exception as e:
                logger.warning(f"Reconstruction légère BM25 impossible : {e}")
        return False

    store = get_store(force_reindex=False)

    if supprimes | modifies:
        remove_files(store, supprimes | modifies, tenant_id=tenant_id)

    # WHY: Purge du semantic cache ciblé sur tous les fichiers qui changent
    # (supprimés, modifiés ET nouveaux). Un fichier "nouveau" peut contredire
    # une réponse existante — ex: v1 du fichier disait X, on ajoute un nouveau
    # fichier qui dit Y, la réponse cachée sur X est périmée.
    fichiers_impactes = supprimes | modifies | nouveaux
    if fichiers_impactes:
        try:
            from src.caching.semantic_cache import invalidate_for_files as _invalidate_semantic_cache
            # _invalidate_semantic_cache est asynchrone
            _run_async(_invalidate_semantic_cache(fichiers_impactes))
        except Exception as e:
            logger.warning(f"Impossible d'invalider le semantic cache : {e}")

    # WHY: les fichiers connus gardent leur indexed_at d'origine (pas écrasé
    # par un edit), les nouveaux reçoivent now.
    new_memory = _build_new_memory(fichiers_actuels, memoire)
    indexed_at_map = _indexed_at_map(new_memory)

    a_indexer = nouveaux | modifies
    new_docs = []
    if a_indexer:
        new_docs = prepare_files_for_ai(a_indexer, indexed_at_map, tenant_id=tenant_id)
        add_documents(store, new_docs)

    # WHY: On reconstruit le corpus BM25 uniquement depuis les fichiers changés +
    # les anciens non modifiés, évitant de tout retraiter.
    unchanged   = actuels - a_indexer - supprimes
    stable_docs = prepare_files_for_ai(unchanged, indexed_at_map, tenant_id=tenant_id)
    _save_bm25_corpus(new_docs + stable_docs)

    save_memory(new_memory)
    logger.info(f"Mise à jour : +{len(nouveaux)} nouveau(x), ~{len(modifies)} modifié(s), -{len(supprimes)} supprimé(s).")
    return True


if __name__ == "__main__":
    index_data(force_reindex=False)
