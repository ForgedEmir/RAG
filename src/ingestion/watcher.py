"""Surveille data/sample/ et déclenche une réindexation en cas de changement.

Debounce 2s pour éviter les réindexations en cascade lors d'un dépôt multi-fichiers.
Fail-silent si watchdog n'est pas installé.
"""
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

DATA_FOLDER   = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
DEBOUNCE_MS   = 2.0   # secondes


class _LoreWatcher:
    def __init__(self):
        self._timer: Optional[threading.Timer] = None
        self._lock  = threading.Lock()
        self._observer = None

    def start(self) -> None:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            class _Handler(FileSystemEventHandler):
                def __init__(self, watcher: "_LoreWatcher"):
                    self._w = watcher

                def on_any_event(self, event):
                    if event.is_directory:
                        return
                    # WHY: On ignore les fichiers temporaires créés par les éditeurs.
                    if any(event.src_path.endswith(ext) for ext in (".tmp", ".swp", "~")):
                        return
                    self._w._schedule_reindex()

            os.makedirs(DATA_FOLDER, exist_ok=True)
            self._observer = Observer()
            self._observer.schedule(_Handler(self), DATA_FOLDER, recursive=False)
            self._observer.start()
            logger.info(f"[WATCHDOG] Surveillance active sur {DATA_FOLDER}")
        except ImportError:
            logger.warning("[WATCHDOG] watchdog non installé — surveillance désactivée. Faire : pip install watchdog")
        except Exception as e:
            logger.warning(f"[WATCHDOG] Démarrage échoué : {e}")

    def stop(self) -> None:
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def _schedule_reindex(self) -> None:
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(DEBOUNCE_MS, self._reindex)
            self._timer.daemon = True
            self._timer.start()

    def _reindex(self) -> None:
        logger.info("[WATCHDOG] Changement détecté — réindexation en cours...")
        try:
            from src.ingestion.run import index_data
            index_data(force_reindex=False)
            logger.info("[WATCHDOG] Réindexation terminée.")
        except Exception as e:
            logger.error(f"[WATCHDOG] Réindexation échouée : {e}")


# Singleton
_watcher = _LoreWatcher()


def start_watchdog() -> None:
    _watcher.start()


def stop_watchdog() -> None:
    _watcher.stop()
