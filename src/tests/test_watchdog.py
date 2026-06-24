"""Unit tests — Watchdog (file change detection)."""
import time
from unittest.mock import patch

import pytest


def test_watchdog_detecte_nouveau_fichier():
    """The watchdog must schedule a reindexing when a file is created."""
    import src.ingestion.watcher as watcher_module
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    with patch.object(watcher_module, "DEBOUNCE_SECONDS", 0.3):
        with patch.object(watcher, "_reindex") as mock_reindex:
            watcher._schedule_reindex("tenant_a")
            time.sleep(0.6)   # attendre le debounce (0.3s)
            mock_reindex.assert_called_once_with("tenant_a")


def test_watchdog_debounce_fusionne_events():
    """Multiple fast events for the same tenant must trigger only one reindexing."""
    import src.ingestion.watcher as watcher_module
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    with patch.object(watcher_module, "DEBOUNCE_SECONDS", 0.3):
        with patch.object(watcher, "_reindex") as mock_reindex:
            for _ in range(10):
                watcher._schedule_reindex("tenant_a")
                time.sleep(0.05)
            time.sleep(0.6)   # attendre le debounce
            assert mock_reindex.call_count == 1
            mock_reindex.assert_called_once_with("tenant_a")


def test_watchdog_fail_sans_package():
    """Without installed watchdog, start() must not crash."""
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    with patch.dict("sys.modules", {"watchdog.observers": None, "watchdog.events": None}):
        with patch("builtins.__import__", side_effect=ImportError("no watchdog")):
            try:
                watcher.start()
            except Exception as e:
                pytest.fail(f"start() raised an exception: {e}")


def test_watchdog_stop_propre():
    """stop() must not raise an exception even if never started."""
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    watcher.stop()   # doit passer sans erreur
