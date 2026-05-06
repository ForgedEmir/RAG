"""
Indexing pipeline for lore files.
Detects new/modified/deleted files and updates Qdrant.
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
SUPPORTED_EXTENSIONS = (".md", ".txt", ".json", ".csv", ".xlsx", ".xls", ".xml", ".pdf", ".docx", ".doc", ".pptx", ".eml", ".msg")
PARSER_MODE         = os.getenv("PARSER", "custom")
_INGESTION_LORE_CLASSIFIER_ENABLED = env_bool("INGESTION_LORE_CLASSIFIER_ENABLED", True)
_INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED = env_bool("INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED", True)
_CHUNK_DEDUP_ENABLED = env_bool("CHUNK_DEDUP_ENABLED", True)
_LATE_CHUNKING_ENABLED = env_bool("LATE_CHUNKING_ENABLED", True)
_LATE_CHUNKING_WINDOW = max(1, int(os.getenv("LATE_CHUNKING_WINDOW", "3")))

_CHUNK_CTX_REDIS_TTL = 86400   # 24h — key "chunk_ctx:{md5_hash}"

# Thread-safe LLM singletons
# _llm_checker    : max_tokens=10  — classifies lore vs non-lore (YES/NO)
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


# ── Redis (optional) ─────────────────────────────────────────────────────────

_redis_client      = None
_redis_client_lock = threading.Lock()

_index_lock = threading.Lock()

def _get_redis():
    """Return a singleton Redis client or None if unavailable. Fail-open."""
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


# ── Indexed-files memory ─────────────────────────────────────────────────────

def _normalize_memory_entry(name: str, raw) -> dict:
    """Normalize a memory entry to {mtime, indexed_at} format.

    Accepts the legacy format (raw = float mtime) for backward compat:
    we hydrate indexed_at = mtime for already-known files, even if it
    loses the "true" date of addition (no better approximation available).
    """
    if isinstance(raw, dict):
        mtime      = float(raw.get("mtime", 0.0) or 0.0)
        indexed_at = float(raw.get("indexed_at", mtime) or mtime)
        return {"mtime": mtime, "indexed_at": indexed_at}
    # Legacy format: raw is a float (mtime)
    try:
        mtime = float(raw)
    except (TypeError, ValueError):
        logger.warning(f"Invalid memory entry for {name}, ignored.")
        return {"mtime": 0.0, "indexed_at": 0.0}
    return {"mtime": mtime, "indexed_at": mtime}


def _bootstrap_memory_from_qdrant() -> Dict[str, dict]:
    """Rebuild the file memory from Qdrant.

    WHY: files_metadata.json lives inside the container (not persisted across restarts).
    When it is missing, we scroll Qdrant to find already-indexed files and rebuild
    the state, avoiding unnecessary re-indexing of the existing files.
    """
    try:
        from src.ingestion.vector_store import _get_client, _COLLECTION_NAME
        client = _get_client()
        seen: Dict[str, dict] = {}
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
                payload   = point.payload or {}
                meta      = payload.get("metadata", {})
                fichier   = meta.get("fichier")
                if not fichier or fichier in seen:
                    continue
                indexed_at = float(meta.get("indexed_at", 0.0) or 0.0)
                fpath      = os.path.join(DATA_FOLDER, fichier)
                mtime      = os.path.getmtime(fpath) if os.path.exists(fpath) else indexed_at
                seen[fichier] = {"mtime": mtime, "indexed_at": indexed_at}
            if offset is None:
                break
        return seen
    except Exception as e:
        logger.warning("Could not bootstrap memory from Qdrant: %s", e)
        return {}


def load_memory() -> Dict[str, dict]:
    """Read the indexed-files tracking file.

    Returns {name: {mtime, indexed_at}}. Silently migrates the legacy format
    {name: mtime_float} to the new one.
    If the file is missing (container restart), tries to rebuild state from
    Qdrant to avoid unnecessary re-indexing.
    """
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return {name: _normalize_memory_entry(name, raw) for name, raw in data.items()}
            logger.warning("Invalid file memory (unexpected type), reset.")
        except json.JSONDecodeError as e:
            try:
                with open(MEMORY_FILE, 'r', encoding='utf-8-sig') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return {name: _normalize_memory_entry(name, raw) for name, raw in data.items()}
            except Exception:
                pass
            logger.warning(f"File memory JSON corrupted, reset: {e}")
        except Exception as e:
            logger.warning(f"Could not read file memory, reset: {e}")

    # File missing — rebuild from Qdrant (typically after a restart)
    logger.info("File memory missing — rebuilding from Qdrant...")
    memory = _bootstrap_memory_from_qdrant()
    if memory:
        save_memory(memory)
        logger.info("File memory rebuilt from Qdrant (%d file(s)).", len(memory))
    return memory


def save_memory(files: dict) -> None:
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(files, f, indent=2)


def list_current_files() -> dict:
    if not os.path.exists(DATA_FOLDER):
        return {}
    files = {}
    for entry in os.scandir(DATA_FOLDER):
        if not entry.is_dir():
            continue
        for root, _, filenames in os.walk(entry.path):
            for name in filenames:
                if name.lower().endswith(SUPPORTED_EXTENSIONS):
                    rel_path = os.path.relpath(os.path.join(root, name), DATA_FOLDER)
                    files[rel_path] = os.path.getmtime(os.path.join(root, name))
    return files


# ── Content validation ───────────────────────────────────────────────────────

def _is_lore_content(text: str, name: str) -> bool:
    """Verify via LLM that the file contains relevant content. Fail-open if LLM unavailable."""
    if not _INGESTION_LORE_CLASSIFIER_ENABLED:
        return True
    try:
        llm      = _get_llm_checker()
        response = llm.invoke([
            SystemMessage(content=(
                "You validate content for a professional knowledge base. "
                "Reply YES if the text contains useful factual, technical, structural or documentary information. "
                "Reply NO if it is purely promotional, empty, or has no informational value. "
                "When in doubt, reply YES."
            )),
            HumanMessage(content=f"File '{name}':\n\n{text[:2000]}"),
        ])
        return "NO" not in response.content.strip().upper().split()
    except Exception as e:
        logger.warning(f"Verification impossible for '{name}', accepted by default: {e}")
        return True


# ── Context-Aware Enrichment ─────────────────────────────────────────────────

def _get_doc_context(text: str, name: str) -> dict:
    """Generate a summary and named entities to enrich each chunk's metadata.

    WHY: Injecting global context into each chunk improves RAG accuracy on
    questions referring to elements mentioned elsewhere in the document.
    Redis cache 24h on the MD5 hash of the text to avoid redundant LLM calls.
    """
    if not _INGESTION_CONTEXTUAL_ENRICHMENT_ENABLED:
        return {"doc_summary": "", "entities": []}

    content_hash = hashlib.md5(text[:5000].encode()).hexdigest()
    redis_key    = f"chunk_ctx:{content_hash}"

    # Try fetching from Redis
    redis_client = _get_redis()
    if redis_client:
        try:
            cached = redis_client.get(redis_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    # LLM call
    context = {"doc_summary": "", "entities": []}
    try:
        result = _get_llm_summarizer().invoke([
            SystemMessage(content=(
                "You analyze documents. Reply in strict JSON (no markdown) with two keys: "
                "'summary' (2-3 sentence summary), "
                "'entities' (list of strings: names of people, places, organizations, artifacts). "
                "Example: {\"summary\": \"...\", \"entities\": [\"Aethon\", \"City of Vael\"]}"
            )),
            HumanMessage(content=f"Document '{name}':\n\n{text[:3000]}"),
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
        logger.warning(f"Doc context impossible for '{name}': {e}")

    # Redis caching
    if redis_client:
        try:
            redis_client.setex(redis_key, _CHUNK_CTX_REDIS_TTL, json.dumps(context))
        except Exception:
            pass

    return context


# ── Indexing pipeline ────────────────────────────────────────────────────────

def _apply_late_chunking(chunks: List[str]) -> List[str]:
    """Prefix each chunk with its preceding neighbors to contextualize the embedding.

    WHY: A chunk embedded alone loses the document context. Prefixing with the
    _LATE_CHUNKING_WINDOW preceding chunks lets the vector capture narrative
    continuity — improves semantic accuracy on questions referencing elements
    mentioned earlier in the document.
    Note: page_content stores the original text for generation; the contextual
    text is only used at embedding time (via add_documents → embedder).
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
    file_names: Set[str],
    indexed_at_map: Dict[str, float] = None,
    tenant_id: str = "",
    data_folder: str = None,
) -> List[Document]:
    """Process files and return Documents ready to index.

    indexed_at_map: {name: timestamp} — original add date for an already-known
    file. If absent (new file), we generate time.time(). This date is preserved
    on re-indexing so a "modified file" doesn't go back to "new file" from the
    conflict-resolution point of view.
    tenant_id: tenant identifier, injected into each chunk for Qdrant isolation.
    data_folder: source folder (defaults to global DATA_FOLDER).

    Pipeline: extract → off-topic check → doc context → split → late chunking → filter
    """
    documents = []
    seen_chunk_hashes: Set[str] = set()
    dedup_skipped = 0
    indexed_at_map = indexed_at_map or {}
    now = time.time()
    folder = data_folder or DATA_FOLDER

    for name in file_names:
        path = os.path.join(folder, name)
        if not os.path.exists(path):
            continue
        indexed_at = float(indexed_at_map.get(name, now))

        try:
            ext = os.path.splitext(name)[1].lower()
            if PARSER_MODE == "unstructured" and ext != ".json":
                from src.ingestion.document_loader import extract_text_with_unstructured
                text = extract_text_with_unstructured(path)
            else:
                raw   = extract_text_from_file(path)
                text  = clean_text(raw) if raw else None

            if not text:
                continue

            if not _is_lore_content(text, name):
                logger.warning(f"'{name}' ignored: off-topic content.")
                continue

            # Global document context (summary + entities) injected into each chunk
            doc_context = _get_doc_context(text, name)

            raw_chunks = split_into_chunks(text)
            # Late chunking: enrich each chunk with its neighbors for embedding
            contextual_chunks = _apply_late_chunking(raw_chunks)

            for chunk_idx, (chunk, contextual_chunk) in enumerate(zip(raw_chunks, contextual_chunks)):
                if not check_patterns(chunk)["valid"]:
                    logger.warning(f"Suspicious chunk ignored in '{name}'.")
                    continue
                # SHA256 on the original chunk (not contextual) for stable dedup
                normalized_chunk = " ".join(chunk.split()).strip().lower()
                chunk_sha256 = hashlib.sha256(normalized_chunk.encode("utf-8")).hexdigest()
                if _CHUNK_DEDUP_ENABLED and chunk_sha256 in seen_chunk_hashes:
                    dedup_skipped += 1
                    continue
                seen_chunk_hashes.add(chunk_sha256)
                chunk_id = f"{name}_{chunk_idx}"
                file_label = f"[Source: {os.path.basename(name)}]\n"
                documents.append(Document(
                    # page_content = contextual text → vector captures neighboring context
                    # Original text is preserved in metadata for generation
                    page_content=file_label + contextual_chunk,
                    metadata={
                        "fichier":        name,
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
            logger.error(f"Error on '{name}': {e}")

    if dedup_skipped:
        logger.info(f"Dedup chunks: {dedup_skipped} duplicate(s) skipped.")
    if _LATE_CHUNKING_ENABLED:
        logger.info(f"Late chunking active (window={_LATE_CHUNKING_WINDOW}).")
    return documents


def _save_bm25_corpus(documents: List[Document]) -> None:
    """Save the chunks as JSON for the BM25 hybrid search."""
    os.makedirs(os.path.dirname(BM25_CORPUS_FILE), exist_ok=True)
    corpus = []
    for i, doc in enumerate(documents):
        raw_text = doc.metadata.get("original_text") if isinstance(doc.metadata, dict) else None
        bm25_text = raw_text if isinstance(raw_text, str) and raw_text.strip() else doc.page_content
        corpus.append({
            "id": doc.metadata.get("chunk_id", f"doc_{i}"),
            "text": bm25_text,
            "fichier": doc.metadata.get("fichier", "unknown"),
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
    logger.info(f"BM25 corpus saved ({len(corpus)} chunks).")

    try:
        from src.search.search import invalidate_bm25_cache
        invalidate_bm25_cache()
    except Exception as e:
        logger.warning(f"Could not invalidate BM25 cache: {e}")


def bootstrap_bm25_from_qdrant(output_path: str) -> bool:
    """Rebuild the BM25 corpus by scrolling through all Qdrant points.

    Called when the corpus file is missing but Qdrant has data.
    Returns True if the corpus could be written, False otherwise.
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
                    "fichier":    metadata.get("fichier", "unknown"),
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
        logger.info("BM25 corpus rebuilt from Qdrant (%d chunks).", len(corpus))
        return True
    except Exception as e:
        logger.warning("Could not bootstrap BM25 from Qdrant: %s", e)
        return False


def _is_bm25_corpus_healthy(expected_files: Set[str]) -> bool:
    """Quickly validate the persistent BM25 corpus.

    WHY: Tests can leave a fake corpus (e.g. file1.md / Chunk), which
    degrades runtime search if no file change is detected.
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

    # Typical test corpus case: no real file from the current dataset.
    if expected_files and not (corpus_files & expected_files):
        return False

    return True


def _build_new_memory(current_files: Dict[str, float], memory: Dict[str, dict]) -> Dict[str, dict]:
    """Build the new memory while preserving indexed_at for already-known files.
    A new file gets indexed_at = now.
    """
    now = time.time()
    result: Dict[str, dict] = {}
    for name, mtime in current_files.items():
        existing    = memory.get(name) or {}
        indexed_at  = float(existing.get("indexed_at", now) or now)
        result[name] = {"mtime": float(mtime), "indexed_at": indexed_at}
    return result


def _indexed_at_map(memory: Dict[str, dict]) -> Dict[str, float]:
    return {name: float(entry.get("indexed_at", 0.0) or 0.0) for name, entry in memory.items()}


def _run_async(coro):
    """Helper to run async code from sync code (thread pool)."""
    import asyncio
    try:
        # In a thread without an event loop (asyncio.to_thread) — create a dedicated loop
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    except Exception:
        # Silent fallback — the cache must not block indexing
        try:
            coro.close()
        except Exception:
            pass


def index_data(force_reindex: bool = False, tenant_id: str = "") -> bool:
    """Update Qdrant with new/modified/deleted files.

    tenant_id: if provided, chunks are tagged and searches/deletions are
    isolated to this tenant. Leave empty for global indexing (admin).
    """
    with _index_lock:
        return _index_data_locked(force_reindex=force_reindex, tenant_id=tenant_id)


def _index_data_locked(force_reindex: bool = False, tenant_id: str = "") -> bool:
    logger.info("Checking files to index (tenant=%s)...", tenant_id or "global")
    current_files = list_current_files()

    if force_reindex:
        # WHY: force_reindex starts from scratch — existing indexed_at values no
        # longer make sense (collection emptied), each file becomes "new" with now.
        new_memory = _build_new_memory(current_files, {})
        store = get_store(force_reindex=True)
        docs  = prepare_files_for_ai(set(current_files.keys()), _indexed_at_map(new_memory), tenant_id=tenant_id)
        if docs:
            add_documents(store, docs)
            _save_bm25_corpus(docs)
            save_memory(new_memory)
            logger.info("Full reindex complete (tenant=%s).", tenant_id or "global")
        else:
            logger.warning("Collection recreated but no valid files found in data/sample.")
        try:
            from src.caching.semantic_cache import clear_all as _clear_semantic_cache
            # _clear_semantic_cache is async
            _run_async(_clear_semantic_cache())
            logger.info("Semantic cache cleared (force_reindex).")
        except Exception as e:
            logger.warning(f"Could not clear semantic cache: {e}")
        return True

    memory   = load_memory()
    current  = set(current_files.keys())
    previous = set(memory.keys())

    deleted  = previous - current
    new      = current - previous
    modified = {n for n in (current & previous) if current_files[n] > float(memory[n].get("mtime", 0.0) or 0.0)}

    if not (deleted or new or modified):
        logger.info("No changes detected.")
        # Qdrant may be empty (restart, reset) even if memory says "all indexed"
        try:
            _store = get_store(force_reindex=False)
            _info = _store.client.get_collection(_store.collection_name)
            if (_info.points_count or 0) == 0 and current:
                logger.warning("Qdrant empty but memory non-empty — forcing reindex.")
                return _index_data_locked(force_reindex=True, tenant_id=tenant_id)
        except Exception as e:
            logger.warning(f"Could not check Qdrant state: {e}")
        if not _is_bm25_corpus_healthy(current):
            logger.info("BM25 corpus missing/invalid — attempting light rebuild from Qdrant.")
            try:
                from src.search.search import _load_bm25
                _load_bm25()
            except Exception as e:
                logger.warning(f"Light BM25 rebuild failed: {e}")
        return False

    store = get_store(force_reindex=False)

    if deleted | modified:
        remove_files(store, deleted | modified, tenant_id=tenant_id)

    # WHY: Targeted semantic cache purge for all changing files (deleted,
    # modified AND new). A "new" file may contradict an existing answer —
    # e.g. v1 of the file said X, we add a new file saying Y, the cached
    # answer about X is stale.
    impacted_files = deleted | modified | new
    if impacted_files:
        try:
            from src.caching.semantic_cache import invalidate_for_files as _invalidate_semantic_cache
            # _invalidate_semantic_cache is async
            _run_async(_invalidate_semantic_cache(impacted_files))
        except Exception as e:
            logger.warning(f"Could not invalidate semantic cache: {e}")

    # WHY: known files keep their original indexed_at (not overwritten by an
    # edit), new ones get now.
    new_memory = _build_new_memory(current_files, memory)
    indexed_at_map = _indexed_at_map(new_memory)

    to_index = new | modified
    new_docs = []
    if to_index:
        new_docs = prepare_files_for_ai(to_index, indexed_at_map, tenant_id=tenant_id)
        add_documents(store, new_docs)

    # WHY: We rebuild the BM25 corpus only from changed files + the unchanged
    # previous ones, avoiding reprocessing everything.
    unchanged   = current - to_index - deleted
    stable_docs = prepare_files_for_ai(unchanged, indexed_at_map, tenant_id=tenant_id)
    _save_bm25_corpus(new_docs + stable_docs)

    save_memory(new_memory)
    logger.info(f"Update: +{len(new)} new, ~{len(modified)} modified, -{len(deleted)} deleted.")
    return True


if __name__ == "__main__":
    index_data(force_reindex=False)
