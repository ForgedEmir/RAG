"""Watches data/sample/ and triggers a reindex on change.

Multi-tenant aware: when a file changes under data/sample/<tenant_id>/,
the watcher extracts the tenant_id from the path and calls
index_data(tenant_id=<tenant_id>) so only that tenant's BM25 corpus
is rebuilt (preserving per-tenant isolation).

Files at the root of data/sample/ (admin uploads) trigger a global
reindex with tenant_id="".

Debounce 10s per tenant to avoid cascading reindexes during multi-file drop.
Fail-silent if watchdog is not installed.
"""
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

DATA_FOLDER   = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
DEBOUNCE_SECONDS = 10.0
WATCHDOG_ENABLED = os.getenv("WATCHDOG_ENABLED", "true").lower() != "false"


def _extract_tenant_id(file_path: str) -> str:
    """Extract tenant_id from a file path under data/sample/.

    Returns "" if the file is at the root of data/sample/ (admin upload).
    Returns the first path component (tenant_id) otherwise.

    Examples:
        data/sample/tenant_a/policy.pdf -> "tenant_a"
        data/sample/tenant_a/sub/report.pdf -> "tenant_a"
        data/sample/policy.pdf -> ""
    """
    try:
        rel = os.path.relpath(file_path, DATA_FOLDER)
        parts = rel.split(os.sep)
        if len(parts) <= 1:
            return ""  # file at root
        return parts[0]
    except Exception:
        return ""


class _LoreWatcher:
    def __init__(self):
        # Per-tenant debounce timers (tenant_id -> Timer).
        # WHY: a single global timer would mix tenant reindexes and re-introduce
        # the T5 leak (one tenant's file change re-tagging another tenant's chunks).
        self._timers: dict[str, threading.Timer] = {}
        self._lock  = threading.Lock()
        self._observer = None
        # Track which tenants are currently being indexed to prevent re-entrancy.
        self._indexing: set[str] = set()
        self._indexing_lock = threading.Lock()

    def start(self) -> None:
        if not WATCHDOG_ENABLED:
            logger.info("[WATCHDOG] Disabled (WATCHDOG_ENABLED=false).")
            return
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def __init__(self, watcher: "_LoreWatcher"):
                    self._w = watcher

                def on_any_event(self, event):
                    if event.is_directory:
                        return
                    # WHY: We ignore temporary files created by editors.
                    if any(event.src_path.endswith(ext) for ext in (".tmp", ".swp", "~")):
                        return
                    tenant_id = _extract_tenant_id(event.src_path)
                    self._w._schedule_reindex(tenant_id)

            os.makedirs(DATA_FOLDER, exist_ok=True)
            self._observer = Observer()
            # WHY: recursive=True so changes in tenant subdirectories are detected.
            # Previously recursive=False meant tenant uploads never triggered reindex.
            self._observer.schedule(_Handler(self), DATA_FOLDER, recursive=True)
            self._observer.start()
            logger.info(f"[WATCHDOG] Active recursive monitoring on {DATA_FOLDER}")
        except ImportError:
            logger.warning("[WATCHDOG] watchdog not installed - monitoring disabled. Run: pip install watchdog")
        except Exception as e:
            logger.warning(f"[WATCHDOG] Startup failed: {e}")

    def stop(self) -> None:
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()

    def _schedule_reindex(self, tenant_id: str) -> None:
        with self._lock:
            if tenant_id in self._timers:
                self._timers[tenant_id].cancel()
            timer = threading.Timer(DEBOUNCE_SECONDS, self._reindex, args=(tenant_id,))
            timer.daemon = True
            timer.start()
            self._timers[tenant_id] = timer

    def _reindex(self, tenant_id: str) -> None:
        # Non-reentrant per-tenant: skip if this tenant is already being indexed.
        with self._indexing_lock:
            if tenant_id in self._indexing:
                logger.info("[WATCHDOG] Reindex already running for tenant=%s, skipping.", tenant_id or "global")
                return
            self._indexing.add(tenant_id)
        label = tenant_id or "global"
        logger.info("[WATCHDOG] Change detected - reindexing tenant=%s...", label)
        try:
            from src.ingestion.run import index_data
            # WHY: pass tenant_id so list_current_files() only scans this tenant's
            # subdirectory and the BM25 corpus is rebuilt with the correct tenant_id.
            index_data(force_reindex=False, tenant_id=tenant_id)
            logger.info("[WATCHDOG] Reindexing complete for tenant=%s.", label)
        except Exception as e:
            logger.error(f"[WATCHDOG] Reindexing failed for tenant={label}: {e}")
        finally:
            with self._indexing_lock:
                self._indexing.discard(tenant_id)
            with self._lock:
                self._timers.pop(tenant_id, None)


# Singleton
_watcher = _LoreWatcher()


def start_watchdog() -> None:
    _watcher.start()


def stop_watchdog() -> None:
    _watcher.stop()
