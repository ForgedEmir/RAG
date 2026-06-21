"""
Tests unitaires pour les helpers d'ingestion d'archives (_is_archive, _extract_archive).
Tous les tests sont offline — aucun service externe requis.
"""
import io
import os
import struct
import tarfile
import zipfile

import pytest

from src.api.blueprints.admin import _extract_archive, _is_archive


# ── _is_archive ───────────────────────────────────────────────────────────────

def test_is_archive_reconnait_zip():
    """Les fichiers .zip sont reconnus comme archives."""
    assert _is_archive("documents.zip") is True


def test_is_archive_reconnait_tar_gz():
    """Les fichiers .tar.gz sont reconnus comme archives."""
    assert _is_archive("export.tar.gz") is True


def test_is_archive_reconnait_tar_bz2():
    """Les fichiers .tar.bz2 sont reconnus comme archives."""
    assert _is_archive("backup.tar.bz2") is True


def test_is_archive_reconnait_tar_xz():
    """Les fichiers .tar.xz sont reconnus comme archives."""
    assert _is_archive("release.tar.xz") is True


def test_is_archive_rejette_documents():
    """Les formats de documents courants ne sont pas des archives."""
    assert _is_archive("rapport.pdf") is False
    assert _is_archive("contrat.docx") is False
    assert _is_archive("data.csv") is False
    assert _is_archive("notes.txt") is False


# ── _extract_archive — cas nominaux ───────────────────────────────────────────

def _make_zip(files: dict[str, bytes]) -> bytes:
    """Builds a ZIP in memory. files = {name: content}"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _make_tar_gz(files: dict[str, bytes]) -> bytes:
    """Builds a .tar.gz in memory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_zip_happy_path(tmp_path):
    """Un ZIP valide avec .txt et .pdf extrait les deux fichiers."""
    content = _make_zip({
        "rapport.txt": b"contenu texte",
        "contrat.pdf": b"%PDF-1.4 fake",
    })
    extracted = _extract_archive(content, "archive.zip", str(tmp_path))
    assert sorted(extracted) == ["contrat.pdf", "rapport.txt"]
    assert (tmp_path / "rapport.txt").read_bytes() == b"contenu texte"
    assert (tmp_path / "contrat.pdf").read_bytes() == b"%PDF-1.4 fake"


def test_tar_gz_happy_path(tmp_path):
    """Un .tar.gz valide avec un .md extrait le fichier."""
    content = _make_tar_gz({"guide.md": b"# Guide\nContenu."})
    extracted = _extract_archive(content, "archive.tar.gz", str(tmp_path))
    assert extracted == ["guide.md"]
    assert (tmp_path / "guide.md").read_bytes() == b"# Guide\nContenu."


# ── _extract_archive — security ───────────────────────────────────────────────

def test_zip_slip_bloque(tmp_path):
    """A directory traversal path (../../evil.txt) must not be written outside the target directory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", b"attaque")
        zf.writestr("legitime.txt", b"ok")
    content = buf.getvalue()

    extracted = _extract_archive(content, "archive.zip", str(tmp_path))
    # Only the legitimate file is extracted
    assert extracted == ["legitime.txt"]
    # Le fichier malveillant n'existe pas hors de tmp_path
    assert not (tmp_path.parent / "evil.txt").exists()
    assert not (tmp_path.parent.parent / "evil.txt").exists()


def test_zip_bomb_bloque(tmp_path):
    """An archive whose declared size exceeds 100 MB raises a ValueError."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as zf:
        # We fake the declared size by writing a small file
        # puis en patchant le champ file_size dans l'index central.
        zf.writestr("gros.txt", b"x")

    # Patch direct : on remplace file_size dans le header central (offset connu)
    # Simple alternative: create many small files to exceed the threshold.
    # On utilise la seconde approche — plus robuste.
    buf2 = io.BytesIO()
    chunk = b"A" * (1024 * 1024)  # 1 Mo par fichier
    with zipfile.ZipFile(buf2, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for i in range(101):
            zf.writestr(f"fichier_{i:03d}.txt", chunk)

    with pytest.raises(ValueError, match="too large"):
        _extract_archive(buf2.getvalue(), "bombe.zip", str(tmp_path))


def test_max_file_count(tmp_path):
    """A ZIP with more than 50 files raises a ValueError."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for i in range(51):
            zf.writestr(f"doc_{i:02d}.txt", b"contenu")

    with pytest.raises(ValueError, match="Too many files"):
        _extract_archive(buf.getvalue(), "trop.zip", str(tmp_path))


def test_extension_non_supportee_ignoree(tmp_path):
    """An .exe file in an archive is silently ignored."""
    content = _make_zip({
        "virus.exe": b"MZ malware",
        "valide.txt": b"contenu ok",
    })
    extracted = _extract_archive(content, "mixte.zip", str(tmp_path))
    assert extracted == ["valide.txt"]
    assert not (tmp_path / "virus.exe").exists()


def test_archive_zip_dans_zip_ignoree(tmp_path):
    """A nested archive (.zip in .zip) is ignored — unsupported extension."""
    inner = _make_zip({"inner.txt": b"interieur"})
    outer = _make_zip({"nested.zip": inner, "doc.md": b"# Doc"})
    extracted = _extract_archive(outer, "outer.zip", str(tmp_path))
    assert extracted == ["doc.md"]
    assert not (tmp_path / "nested.zip").exists()


def test_archive_vide_retourne_liste_vide(tmp_path):
    """Un ZIP ne contenant aucun fichier valide retourne une liste vide."""
    content = _make_zip({"script.sh": b"#!/bin/bash", "prog.exe": b"MZ"})
    extracted = _extract_archive(content, "invalides.zip", str(tmp_path))
    assert extracted == []
