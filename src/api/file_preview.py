"""
On-demand conversion of office documents to PDF for browser preview.
Uses LibreOffice headless. Cached on disk by source-file mtime.
"""
import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

PREVIEW_CACHE_DIRNAME = ".preview"
SOFFICE_TIMEOUT_SEC = 60

CONVERTIBLE_EXTS = {".pptx", ".ppt", ".docx", ".doc", ".xlsx", ".xls"}

_conversion_lock = asyncio.Lock()


def _cache_path_for(source_path: str) -> str:
    """Return the cached PDF path next to the source file, in a .preview subdir."""
    parent = os.path.dirname(source_path)
    base = os.path.splitext(os.path.basename(source_path))[0]
    cache_dir = os.path.join(parent, PREVIEW_CACHE_DIRNAME)
    return os.path.join(cache_dir, f"{base}.pdf")


def _cache_is_fresh(source_path: str, cache_path: str) -> bool:
    if not os.path.isfile(cache_path):
        return False
    try:
        return os.path.getmtime(cache_path) >= os.path.getmtime(source_path)
    except OSError:
        return False


def _run_soffice(source_path: str, out_dir: str) -> None:
    """Invoke LibreOffice headless to convert source -> PDF in out_dir."""
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pdf",
        "--outdir", out_dir,
        source_path,
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=SOFFICE_TIMEOUT_SEC,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"soffice failed (code={result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )


async def convert_to_pdf(source_path: str) -> Optional[str]:
    """Convert an office document to PDF, return the cached PDF path.
    Returns None if the source extension is not convertible or LibreOffice is missing."""
    ext = os.path.splitext(source_path)[1].lower()
    if ext not in CONVERTIBLE_EXTS:
        return None
    if not os.path.isfile(source_path):
        return None
    if shutil.which("soffice") is None:
        logger.warning("[PREVIEW] soffice not found in PATH, cannot convert %s", source_path)
        return None

    cache_path = _cache_path_for(source_path)
    if _cache_is_fresh(source_path, cache_path):
        return cache_path

    async with _conversion_lock:
        # Double-check after acquiring the lock
        if _cache_is_fresh(source_path, cache_path):
            return cache_path

        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix="soffice_") as tmpdir:
                await asyncio.to_thread(_run_soffice, source_path, tmpdir)
                produced = os.path.join(
                    tmpdir,
                    os.path.splitext(os.path.basename(source_path))[0] + ".pdf",
                )
                if not os.path.isfile(produced):
                    logger.error("[PREVIEW] soffice produced no PDF for %s", source_path)
                    return None
                shutil.move(produced, cache_path)
                logger.info("[PREVIEW] Converted %s -> %s", os.path.basename(source_path), cache_path)
                return cache_path
        except subprocess.TimeoutExpired:
            logger.error("[PREVIEW] soffice timeout for %s", source_path)
            return None
        except Exception as e:
            logger.error("[PREVIEW] Conversion failed for %s: %s", source_path, e)
            return None
