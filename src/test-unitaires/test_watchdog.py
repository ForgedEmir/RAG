"""Tests unitaires — Watchdog (détection changements de fichiers)."""
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest


def test_watchdog_detecte_nouveau_fichier():
    """Le watchdog doit planifier une réindexation à la création d'un fichier."""
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    reindex_called = []

    with patch("src.ingestion.run.index_data", side_effect=lambda **kw: reindex_called.append(True)):
        # Simuler un appel _schedule_reindex
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(watcher, "_reindex") as mock_reindex:
                watcher._schedule_reindex()
                time.sleep(2.5)   # attendre le debounce (2s)
                mock_reindex.assert_called_once()


def test_watchdog_debounce_fusionne_events():
    """Plusieurs events rapides ne doivent déclencher qu'une seule réindexation."""
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    with patch.object(watcher, "_reindex") as mock_reindex:
        for _ in range(10):
            watcher._schedule_reindex()
            time.sleep(0.1)
        time.sleep(2.5)   # attendre le debounce
        assert mock_reindex.call_count == 1


def test_watchdog_fail_sans_package():
    """Sans watchdog installé, start() ne doit pas crasher."""
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    with patch.dict("sys.modules", {"watchdog.observers": None, "watchdog.events": None}):
        with patch("builtins.__import__", side_effect=ImportError("no watchdog")):
            try:
                watcher.start()
            except Exception as e:
                pytest.fail(f"start() a levé une exception : {e}")


def test_watchdog_stop_propre():
    """stop() ne doit pas lever d'exception même si jamais démarré."""
    from src.ingestion.watcher import _LoreWatcher

    watcher = _LoreWatcher()
    watcher.stop()   # doit passer sans erreur
