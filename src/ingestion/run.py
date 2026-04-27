"""
Pipeline d'indexation des documents.
Détecte les fichiers nouveaux/modifiés/supprimés et met à jour Qdrant.
Supporte le chunking narratif (MD, TXT, etc.) et tabulaire (CSV, XLSX).
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
from src.ingestion.chunker import split_into_chunks, split_tabular_csv, split_tabular_xlsx
from src.ingestion.parser import extract_text_from_file, clean_text, read_csv_raw, read_xlsx_sheets
from src.ingestion.vector_store import get_store, add_documents, remove_files
from src.security.validator import check_patterns

logger = logging.getLogger(__name__)

DATA_FOLDER         = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
_DATA_DIR           = os.path.join(os.path.dirname(__file__), "qdrant_db")
MEMORY_FILE         = os.path.join(_DATA_DIR, "files_metadata.json")
BM25_CORPUS_FILE    = os.path.join(_DATA_DIR, "bm25_corpus.json")
SUPPORTED_EXTENSIONS = (".md", ".txt", ".json", ".csv", ".xlsx", ".xml", ".pdf")
PARSER_MODE         = os.getenv("PARSER", "custom")
_INGESTION_LORE_CLASSIFIER_ENABLED = env_bool("INGESTION_LORE_CLASSIFIER_ENABLED", False)
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
    return {
        nom: os.path.getmtime(os.path.join(DATA_FOLDER, nom))
        for nom in os.listdir(DATA_FOLDER)
        if nom.lower().endswith(SUPPORTED_EXTENSIONS)
    }


# ── Validation du contenu ────────────────────────────────────────────────────

def _is_relevant_content(texte: str, nom: str) -> bool:
    """Vérifie via LLM que le fichier contient du contenu informatif pertinent.
    Fail-open si LLM indisponible ou feature désactivée.
    WHY: Anciennement '_is_lore_content' avec un prompt spécifique au lore de jeu vidéo.
    Remplacé par un classificateur généraliste adapté à un RAG documentaire."""
    if not _INGESTION_LORE_CLASSIFIER_ENABLED:
        return True
    try:
        llm      = _get_llm_checker()
        response = llm.invoke([
            SystemMessage(content=(
                "Tu valides du contenu pour une base documentaire généraliste. "
                "Réponds OUI si le texte contient des informations utiles (données, faits, descriptions, listes, etc.). "
                "Réponds NON si c'est clairement du bruit (logs système, fichiers binaires, contenu aléatoire). "
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
                "Tu analyses un document pour une base documentaire généraliste. "
                "Réponds en JSON strict (pas de markdown) avec deux clés : "
                "'summary' (résumé 2-3 phrases du contenu), "
                "'entities' (liste de strings : noms propres, lieux, concepts clés, termes importants). "
                "Exemple : {\"summary\": \"...\", \"entities\": [\"terme1\", \"terme2\"]}"
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

def _chunk_tabular_file(chemin: str, nom: str, ext: str) -> List[str]:
    """Route le chunking tabulaire en fonction de l'extension du fichier.

    WHY: Les fichiers CSV/XLSX doivent être chunkés différemment du texte narratif.
    Chaque groupe de lignes devient un chunk auto-suffisant avec les headers répétés,
    permettant une recherche précise même sur des fichiers de plusieurs centaines de lignes.

    Args:
        chemin: Chemin absolu vers le fichier.
        nom: Nom du fichier (pour les métadonnées et logs).
        ext: Extension du fichier ('.csv' ou '.xlsx').

    Returns:
        Liste de chunks textuels prêts à être indexés.
    """
    try:
        if ext == ".csv":
            headers, data_rows = read_csv_raw(chemin)
            if not headers or not data_rows:
                logger.warning(f"CSV '{nom}' vide ou illisible, fallback texte plat.")
                brut = extract_text_from_file(chemin)
                return split_into_chunks(brut) if brut else []
            return _chunk_csv_from_parsed(headers, data_rows, nom)

        elif ext == ".xlsx":
            sheets = read_xlsx_sheets(chemin)
            if not sheets:
                logger.warning(f"XLSX '{nom}' vide ou illisible, fallback texte plat.")
                brut = extract_text_from_file(chemin)
                return split_into_chunks(brut) if brut else []
            all_chunks: List[str] = []
            for sheet_name, headers, data_rows in sheets:
                chunks = split_tabular_xlsx(data_rows, headers, nom, sheet_name)
                all_chunks.extend(chunks)
            return all_chunks

        else:
            # Ne devrait pas arriver, mais fallback sécurisé
            brut = extract_text_from_file(chemin)
            return split_into_chunks(brut) if brut else []

    except Exception as e:
        logger.error(f"Erreur chunking tabulaire pour '{nom}' : {e}. Fallback texte plat.")
        try:
            brut = extract_text_from_file(chemin)
            return split_into_chunks(brut) if brut else []
        except Exception:
            return []


def _chunk_csv_from_parsed(headers: List[str], data_rows: List[List[str]], filename: str) -> List[str]:
    """Chunking tabulaire CSV à partir de données déjà parsées.

    WHY: split_tabular_csv prend du texte brut, mais on a déjà parsé via read_csv_raw.
    Cette fonction évite de re-parser le fichier.
    """
    import io
    import csv as csv_mod

    # Reconstruire le texte CSV brut pour réutiliser split_tabular_csv
    # C'est plus simple et plus maintenable que de dupliquer la logique
    output = io.StringIO()
    writer = csv_mod.writer(output, delimiter=";")
    writer.writerow(headers)
    for row in data_rows:
        writer.writerow(row)
    csv_text = output.getvalue()

    return split_tabular_csv(csv_text, delimiter=";", filename=filename)


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
) -> List[Document]:
    """Traite les fichiers et retourne des Documents prêts à indexer.

    indexed_at_map : {nom: timestamp} — date d'ajout originale d'un fichier déjà
    connu. Si absent (nouveau fichier), on génère time.time(). Cette date est
    préservée au re-indexing pour que "fichier modifié" ne redevienne pas
    "fichier nouveau" du point de vue résolution de conflit.

    Pipeline : extraction → vérif hors-sujet → contexte doc → découpage → late chunking → filtrage
    """
    documents = []
    seen_chunk_hashes: Set[str] = set()
    dedup_skipped = 0
    indexed_at_map = indexed_at_map or {}
    now = time.time()

    for nom in noms_fichiers:
        chemin = os.path.join(DATA_FOLDER, nom)
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

            if not _is_relevant_content(texte, nom):
                logger.warning(f"'{nom}' ignoré : contenu non pertinent.")
                continue

            # Contexte global du document (résumé + entités) injecté dans chaque chunk
            doc_context = _get_doc_context(texte, nom)

            # ── Routage tabulaire vs narratif ────────────────────────────────
            # WHY: Les fichiers CSV/XLSX nécessitent un chunking spécial qui préserve
            # la structure tabulaire (1 ligne = 1 chunk avec headers répétés).
            # Le RecursiveCharacterTextSplitter standard détruit cette structure.
            is_tabular = ext in (".csv", ".xlsx")

            if is_tabular:
                raw_chunks = _chunk_tabular_file(chemin, nom, ext)
                # Pas de late chunking pour les données tabulaires :
                # les chunks sont déjà auto-suffisants (headers répétés)
                contextual_chunks = raw_chunks
            else:
                raw_chunks = split_into_chunks(texte)
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


def bootstrap_bm25_from_qdrant(target_path: str) -> bool:
    """Reconstruit le corpus BM25 à partir des données présentes dans Qdrant.

    WHY: Si le fichier bm25_corpus.json est absent (p.ex. après un crash ou un
    nettoyage manuel), on peut le reconstruire depuis Qdrant sans réindexer
    tous les fichiers. C'est un bootstrap léger qui itère sur les points Qdrant.

    Args:
        target_path: Chemin où sauvegarder le corpus JSON.

    Returns:
        True si le corpus a été reconstruit avec succès, False sinon.
    """
    try:
        from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
        client = _get_client()

        # Vérifier que la collection existe et contient des points
        try:
            count = client.count(_COLLECTION_NAME).count
        except Exception:
            return False

        if count == 0:
            logger.info("Bootstrap BM25: Qdrant vide, aucun corpus à reconstruire.")
            return False

        # Paginer à travers tous les points pour reconstruire le corpus
        corpus = []
        offset = None
        batch_size = 500

        while True:
            records, offset = client.scroll(
                collection_name=_COLLECTION_NAME,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )

            for record in records:
                payload = record.payload or {}
                raw_text = payload.get("original_text")
                bm25_text = raw_text if isinstance(raw_text, str) and raw_text.strip() else payload.get("page_content", "")
                if not bm25_text or not bm25_text.strip():
                    continue
                corpus.append({
                    "id": payload.get("chunk_id", str(record.id)),
                    "text": bm25_text,
                    "fichier": payload.get("fichier", "inconnu"),
                    "indexed_at": float(payload.get("indexed_at", 0.0) or 0.0),
                })

            if offset is None:
                break

        if not corpus:
            return False

        # Sauvegarder le corpus
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        dirpath = os.path.dirname(target_path)
        fd, tmp_path = tempfile.mkstemp(prefix="bm25_bootstrap_", suffix=".json", dir=dirpath)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(corpus, f, ensure_ascii=False, indent=1)
            os.replace(tmp_path, target_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        logger.info(f"Bootstrap BM25 depuis Qdrant : {len(corpus)} chunks reconstruits.")
        return True

    except Exception as e:
        logger.warning(f"Bootstrap BM25 depuis Qdrant échoué : {e}")
        return False


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


def _invalidate_cache_sync(filenames) -> None:
    """Invalidation du semantic cache via le client Redis synchrone.

    WHY: index_data est une fonction synchrone qui peut être appelée depuis
    n'importe quel thread (asyncio.to_thread, timer watchdog, tests).
    On ne peut PAS y lancer de coroutines async car les asyncio.Lock() du
    module semantic_cache sont liés à l'event loop principal.
    On utilise donc le client Redis synchrone déjà disponible (_get_redis) pour
    faire la purge directement, sans passer par l'API async.
    """
    if not filenames:
        return
    targets = {f for f in filenames if f}
    if not targets:
        return
    try:
        r = _get_redis()
        if not r:
            return
        prefix = "scache:"
        to_delete = []
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{prefix}emb:*", count=500)
            if not keys:
                if cursor == 0:
                    break
                continue
            raw_values = r.mget(keys)
            for key, raw in zip(keys, raw_values):
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except Exception:
                    continue
                if "source_files" not in parsed:
                    should_delete = True
                else:
                    sources = set(parsed.get("source_files") or [])
                    should_delete = bool(sources & targets)
                if should_delete:
                    resp_key = key.replace(f"{prefix}emb:", f"{prefix}resp:")
                    to_delete.extend([key, resp_key])
            if cursor == 0:
                break
        removed_pairs = 0
        if to_delete:
            batch_size = 500
            for i in range(0, len(to_delete), batch_size):
                r.delete(*to_delete[i:i + batch_size])
            removed_pairs = len(to_delete) // 2
            try:
                r.decrby(f"{prefix}meta:count", removed_pairs)
                count_raw = r.get(f"{prefix}meta:count")
                current = int(count_raw or 0)
                if current < 0:
                    r.set(f"{prefix}meta:count", 0)
            except Exception:
                pass
            logger.info(f"Semantic cache : {removed_pairs} entrée(s) invalidée(s) pour {sorted(targets)}.")
    except Exception as e:
        logger.warning(f"Invalidation sync du semantic cache échouée : {e}")


def _clear_cache_sync() -> None:
    """Purge complète du semantic cache via le client Redis synchrone.

    WHY: Même raisonnement que _invalidate_cache_sync — on reste 100% synchrone
    pour éviter les problèmes d'event loop croisé.
    """
    try:
        r = _get_redis()
        if not r:
            return
        prefix = "scache:"
        cursor = 0
        while True:
            cursor, keys = r.scan(cursor, match=f"{prefix}*", count=500)
            if keys:
                r.delete(*keys)
            if cursor == 0:
                break
        try:
            r.delete(f"{prefix}meta:count")
        except Exception:
            pass
        logger.info("Semantic cache vidé (sync).")
    except Exception as e:
        logger.warning(f"Purge sync du semantic cache échouée : {e}")


def index_data(force_reindex: bool = False) -> bool:
    """Met à jour Qdrant avec les fichiers nouveaux/modifiés/supprimés."""
    logger.info("Vérification des fichiers documentaires...")
    fichiers_actuels = list_current_files()

    if force_reindex:
        # WHY: force_reindex repart de zéro — les indexed_at existants n'ont plus
        # de sens (collection vidée), chaque fichier devient "nouveau" avec now.
        new_memory = _build_new_memory(fichiers_actuels, {})
        store = get_store(force_reindex=True)
        docs  = prepare_files_for_ai(set(fichiers_actuels.keys()), _indexed_at_map(new_memory))
        if docs:
            add_documents(store, docs)
            _save_bm25_corpus(docs)
            save_memory(new_memory)
            logger.info("Réindexation complète terminée.")
        else:
            logger.warning("Collection recréée mais aucun fichier valide trouvé dans data/sample.")
        try:
            _clear_cache_sync()
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
        remove_files(store, supprimes | modifies)

    # WHY: Purge du semantic cache ciblé sur tous les fichiers qui changent
    # (supprimés, modifiés ET nouveaux). Un fichier "nouveau" peut contredire
    # une réponse existante — ex: v1 du fichier disait X, on ajoute un nouveau
    # fichier qui dit Y, la réponse cachée sur X est périmée.
    fichiers_impactes = supprimes | modifies | nouveaux
    if fichiers_impactes:
        _invalidate_cache_sync(fichiers_impactes)

    # WHY: les fichiers connus gardent leur indexed_at d'origine (pas écrasé
    # par un edit), les nouveaux reçoivent now.
    new_memory = _build_new_memory(fichiers_actuels, memoire)
    indexed_at_map = _indexed_at_map(new_memory)

    a_indexer = nouveaux | modifies
    new_docs = []
    if a_indexer:
        new_docs = prepare_files_for_ai(a_indexer, indexed_at_map)
        add_documents(store, new_docs)

    # WHY: On reconstruit le corpus BM25 uniquement depuis les fichiers changés +
    # les anciens non modifiés, évitant de tout retraiter.
    unchanged   = actuels - a_indexer - supprimes
    stable_docs = prepare_files_for_ai(unchanged, indexed_at_map)
    _save_bm25_corpus(new_docs + stable_docs)

    save_memory(new_memory)
    logger.info(f"Mise à jour : +{len(nouveaux)} nouveau(x), ~{len(modifies)} modifié(s), -{len(supprimes)} supprimé(s).")
    return True


if __name__ == "__main__":
    index_data(force_reindex=False)
