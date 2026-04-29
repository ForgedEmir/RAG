import asyncio
import io
import logging
import mimetypes
import os
import re
import tarfile
import zipfile
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from src.api.auth import get_current_user, get_tenant_id, require_monitoring
from src.api.limiter import limiter
from src.ingestion.run import index_data, SUPPORTED_EXTENSIONS
from src.monitoring.tracker import track
from src.security.validator import valider_entree

logger = logging.getLogger(__name__)
admin_router = APIRouter()

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE_KB", "500")) * 1024
MAX_ARCHIVE_SIZE = int(os.getenv("MAX_ARCHIVE_SIZE_MB", "50")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".xlsx", ".pdf", ".docx", ".doc"}
ARCHIVE_EXTENSIONS = {".zip", ".tar.gz", ".tar.bz2", ".tar.xz"}
MAX_ARCHIVE_FILES = 50
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB
DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "sample"))
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._ -]{1,120}$")


def _sanitize_filename(raw_name: str) -> str:
    """Return a safe basename or an empty string when invalid."""
    name = os.path.basename((raw_name or "").replace("\x00", "")).strip()
    if not name or name in {".", ".."}:
        return ""
    if any(sep in name for sep in ("/", "\\")):
        return ""
    if ".." in name:
        return ""
    if not _SAFE_FILENAME_RE.match(name):
        return ""
    return name


def _is_archive(filename: str) -> bool:
    name = filename.lower()
    return any(name.endswith(ext) for ext in ARCHIVE_EXTENSIONS)


def _extract_archive(content: bytes, filename: str, target_dir: str) -> list[str]:
    """Extract archive safely into target_dir. Returns list of filenames written to disk.

    Enforces: zip-slip protection, zip-bomb limit, file count limit, extension filtering.
    """
    name = filename.lower()
    real_target = os.path.realpath(target_dir)
    extracted: list[str] = []

    def _safe_write(data: bytes, basename: str) -> str | None:
        safe = _sanitize_filename(basename)
        if not safe:
            return None
        if os.path.splitext(safe)[1].lower() not in ALLOWED_EXTENSIONS:
            return None
        dest = os.path.join(target_dir, safe)
        # Zip-slip guard: resolved destination must stay inside target_dir
        if not os.path.realpath(dest).startswith(real_target + os.sep):
            logger.warning("[ARCHIVE] Zip-slip blocked: '%s'", basename)
            return None
        with open(dest, "wb") as f:
            f.write(data)
        return safe

    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            total = sum(i.file_size for i in infos)
            if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"Decompressed archive too large "
                    f"({total // 1024 // 1024} MB > {MAX_ARCHIVE_UNCOMPRESSED_BYTES // 1024 // 1024} MB max)"
                )
            if len(infos) > MAX_ARCHIVE_FILES:
                raise ValueError(f"Too many files in the archive ({len(infos)} > {MAX_ARCHIVE_FILES} max)")
            for info in infos:
                if os.path.isabs(info.filename) or ".." in info.filename.replace("\\", "/").split("/"):
                    logger.warning("[ARCHIVE] Zip-slip blocked: '%s'", info.filename)
                    continue
                with zf.open(info) as src:
                    saved = _safe_write(src.read(), os.path.basename(info.filename))
                    if saved:
                        extracted.append(saved)
    else:
        mode = (
            "r:gz" if name.endswith(".tar.gz") else
            "r:bz2" if name.endswith(".tar.bz2") else
            "r:xz" if name.endswith(".tar.xz") else
            "r:"
        )
        with tarfile.open(fileobj=io.BytesIO(content), mode=mode) as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            total = sum(m.size for m in members)
            if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise ValueError(
                    f"Decompressed archive too large "
                    f"({total // 1024 // 1024} MB > {MAX_ARCHIVE_UNCOMPRESSED_BYTES // 1024 // 1024} MB max)"
                )
            if len(members) > MAX_ARCHIVE_FILES:
                raise ValueError(f"Too many files in the archive ({len(members)} > {MAX_ARCHIVE_FILES} max)")
            for member in members:
                fobj = tf.extractfile(member)
                if fobj:
                    saved = _safe_write(fobj.read(), os.path.basename(member.name))
                    if saved:
                        extracted.append(saved)

    return extracted


def _count_points_for_filename(filename: str) -> int | None:
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        from src.ingestion.vector_store import get_store
        store = get_store(force_reindex=False)
        result = store.client.count(
            collection_name="knowledge",
            count_filter=Filter(
                should=[FieldCondition(key="metadata.filename", match=MatchValue(value=filename))]
            ),
            exact=True,
        )
        return int(getattr(result, "count", 0))
    except Exception as e:
        logger.warning(f"Qdrant check impossible for '{filename}': {e}")
        return None


def _read_sample(content: bytes, ext: str, safe_name: str) -> str:
    """Extracts a text sample for security validation."""
    text = content.decode("utf-8", errors="ignore") if ext in {".txt", ".md", ".csv", ".json", ".xml"} else ""
    lines = text.splitlines()
    if len(lines) > 40:
        mid = len(lines) // 2
        return "\n".join(lines[:20] + lines[max(0, mid - 5):mid + 5] + lines[-20:])
    if not text and ext in {".pdf", ".xlsx"}:
        return f"BINARY_FILE:{ext}:{safe_name}:{len(content)}"
    return text


# ── /api/upload endpoint — accessible to all authenticated users ───────────

@admin_router.post("/api/upload")
@limiter.limit("10/hour")
async def tenant_upload(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Multi-tenant upload: validates → Supabase Storage → Qdrant ingestion with tenant_id."""
    tenant_id = await get_tenant_id(user_id)

    safe_name = _sanitize_filename(file.filename or "")
    if not safe_name:
        return JSONResponse({"error": "Invalid filename."}, status_code=400)

    is_arch = _is_archive(safe_name)
    ext = os.path.splitext(safe_name)[1].lower()
    if not is_arch and ext not in ALLOWED_EXTENSIONS:
        all_formats = sorted(ALLOWED_EXTENSIONS | ARCHIVE_EXTENSIONS)
        return JSONResponse(
            {"error": f"Unsupported extension. Formats: {', '.join(all_formats)}"},
            status_code=400,
        )

    content = await file.read()
    if not content:
        return JSONResponse({"error": "Empty file."}, status_code=400)

    size_limit = MAX_ARCHIVE_SIZE if is_arch else MAX_UPLOAD_SIZE
    if len(content) > size_limit:
        size_kb = len(content) // 1024
        return JSONResponse(
            {"error": f"File too large ({size_kb} KB). Max: {size_limit // 1024} KB."},
            status_code=400,
        )

    tenant_data_dir = os.path.join(DATA_DIR, tenant_id)
    os.makedirs(tenant_data_dir, exist_ok=True)

    # ── Archive path ─────────────────────────────────────────────────────────
    if is_arch:
        try:
            extracted_names = _extract_archive(content, safe_name, tenant_data_dir)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        if not extracted_names:
            return JSONResponse(
                {"error": "No valid file found in the archive (accepted formats: "
                          f"{', '.join(sorted(ALLOWED_EXTENSIONS))})."},
                status_code=400,
            )

        storage_ok_count = 0
        try:
            from src.monitoring.tracker import _get_client
            supa = await _get_client()
            if supa:
                for fname in extracted_names:
                    fpath = os.path.join(tenant_data_dir, fname)
                    with open(fpath, "rb") as fh:
                        fdata = fh.read()
                    try:
                        await supa.storage.from_("tenant-docs").upload(
                            path=f"{tenant_id}/{fname}",
                            file=fdata,
                            file_options={"content-type": "application/octet-stream", "upsert": "true"},
                        )
                        storage_ok_count += 1
                    except Exception as e:
                        logger.warning("[UPLOAD] Supabase Storage failed for '%s/%s': %s", tenant_id, fname, e)
        except Exception as e:
            logger.warning("[UPLOAD] Supabase Storage archive failed: %s", e)

        async def _run_ingestion_archive():
            try:
                from src.ingestion.run import index_data as _index
                await asyncio.to_thread(_index, False, tenant_id)
                logger.info("[UPLOAD] Archive ingestion OK — tenant=%s files=%s", tenant_id, extracted_names)
            except Exception as e:
                logger.error("[UPLOAD] Archive ingestion failed — tenant=%s : %s", tenant_id, e)

        asyncio.create_task(_run_ingestion_archive())
        await track("upload", detail=f"tenant={tenant_id} | archive={safe_name} | {len(extracted_names)} files")
        return {
            "message": f"{len(extracted_names)} file(s) extracted from '{safe_name}'. Ingestion in progress.",
            "files": extracted_names,
            "count": len(extracted_names),
            "tenant_id": tenant_id,
            "storage_ok": storage_ok_count,
        }

    # ── Regular file path (unchanged) ────────────────────────────────────────
    sample = _read_sample(content, ext, safe_name)
    validation = await valider_entree(sample)
    if not validation["valid"]:
        logger.warning(f"[UPLOAD] Blocked [{validation['type']}] tenant={tenant_id} file='{safe_name}'")
        await track("upload_blocked", detail=f"tenant={tenant_id} | {safe_name} | {validation['type']}")
        return JSONResponse({"error": "Suspicious content. Upload rejected."}, status_code=400)

    # ── Supabase Storage (bucket "tenant-docs", path "tenant_id/filename") ──
    storage_path = f"{tenant_id}/{safe_name}"
    storage_ok = False
    try:
        from src.monitoring.tracker import _get_client
        supa = await _get_client()
        if supa:
            await supa.storage.from_("tenant-docs").upload(
                path=storage_path,
                file=content,
                file_options={
                    "content-type": file.content_type or "application/octet-stream",
                    "upsert": "true",
                },
            )
            storage_ok = True
            logger.info(f"[UPLOAD] Supabase Storage OK: {storage_path}")
    except Exception as e:
        logger.warning(f"[UPLOAD] Supabase Storage failed for '{storage_path}': {e}")

    # ── Local write in data/sample/<tenant_id>/ for the pipeline ──────
    destination = os.path.join(tenant_data_dir, safe_name)
    existed_before = os.path.exists(destination)
    with open(destination, "wb") as f:
        f.write(content)

    # ── Background ingestion (non-blocking) ─────────────────────────────
    async def _run_ingestion():
        try:
            from src.ingestion.run import index_data as _index
            await asyncio.to_thread(_index, False, tenant_id)
            logger.info(f"[UPLOAD] Ingestion OK — tenant={tenant_id} file={safe_name}")
        except Exception as e:
            logger.error(f"[UPLOAD] Ingestion failed — tenant={tenant_id} : {e}")

    asyncio.create_task(_run_ingestion())

    action = "replace" if existed_before else "upload"
    await track(action, detail=f"tenant={tenant_id} | {safe_name} | {len(content) // 1024} KB")
    return {
        "message": f"'{safe_name}' {'replaced' if existed_before else 'uploaded'}. Ingestion in progress.",
        "filename": safe_name,
        "tenant_id": tenant_id,
        "storage_path": storage_path,
        "storage_ok": storage_ok,
    }


# ── Admin routes ──────────────────────────────────────────────────────────────

@admin_router.get("/api/admin/sources")
async def admin_sources(request: Request):
    require_monitoring(request)
    from src.ingestion.run import list_current_files
    files = list_current_files()
    return {"files": sorted(files.keys()), "total": len(files)}


@admin_router.get("/api/sources")
async def user_sources(user_id: str = Depends(get_current_user)):
    tenant_id = await get_tenant_id(user_id)
    tenant_dir = os.path.join(DATA_DIR, tenant_id)
    if not os.path.isdir(tenant_dir):
        return {"files": [], "total": 0}
    files = sorted(
        f for f in os.listdir(tenant_dir)
        if os.path.isfile(os.path.join(tenant_dir, f))
        and os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
    )
    return {"files": files, "total": len(files)}


@admin_router.post("/api/admin/upload")
@limiter.limit("20/hour")
async def admin_upload(request: Request, file: UploadFile = File(...)):
    require_monitoring(request)

    safe_name = _sanitize_filename(file.filename or "")
    if not safe_name:
        return JSONResponse({"error": "Invalid filename."}, status_code=400)

    is_arch = _is_archive(safe_name)
    ext = os.path.splitext(safe_name)[1].lower()
    if not is_arch and ext not in ALLOWED_EXTENSIONS:
        return JSONResponse({"error": f"Unsupported extension. Formats: {', '.join(ALLOWED_EXTENSIONS)}"}, status_code=400)

    content = await file.read()
    if not content:
        return JSONResponse({"error": "Empty file."}, status_code=400)

    size_limit = MAX_ARCHIVE_SIZE if is_arch else MAX_UPLOAD_SIZE
    if len(content) > size_limit:
        size_kb, limit_kb = len(content) // 1024, size_limit // 1024
        return JSONResponse({"error": f"File too large ({size_kb} KB). Max: {limit_kb} KB."}, status_code=400)

    os.makedirs(DATA_DIR, exist_ok=True)

    # ── Archive path ─────────────────────────────────────────────────────────
    if is_arch:
        try:
            extracted_names = _extract_archive(content, safe_name, DATA_DIR)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

        if not extracted_names:
            return JSONResponse(
                {"error": f"No valid file found in the archive (accepted formats: {', '.join(sorted(ALLOWED_EXTENSIONS))})."},
                status_code=400,
            )

        changed = None
        reindex_warning = None
        try:
            changed = bool(await asyncio.to_thread(index_data, force_reindex=False))
        except Exception as e:
            reindex_warning = str(e)
            logger.warning("Admin archive reindexing failed: %s", e)

        await track("upload", detail=f"archive={safe_name} | {len(extracted_names)} files")
        payload = {
            "message": f"{len(extracted_names)} file(s) extracted from '{safe_name}' and indexed.",
            "files": extracted_names,
            "count": len(extracted_names),
            "ingestion": {"changed": changed},
        }
        if reindex_warning:
            payload["warning"] = "Files extracted, but automatic reindexing failed."
        return payload

    # ── Regular file path (unchanged) ────────────────────────────────────────
    try:
        text = content.decode("utf-8", errors="ignore") if ext in {".txt", ".md", ".csv", ".json", ".xml"} else ""
    except Exception:
        return JSONResponse({"error": "Invalid encoding."}, status_code=400)

    # Security check on a representative sample to avoid high latency on large files
    lines = text.splitlines()
    if len(lines) > 50:
        mid = len(lines) // 2
        sample = "\n".join(lines[:20] + lines[max(0, mid - 5):mid + 5] + lines[-20:])
    else:
        sample = text

    # Binary formats: shallow marker for validator path, keep low latency.
    if not sample and ext in {".pdf", ".xlsx"}:
        sample = f"BINARY_FILE:{ext}:{safe_name}:{len(content)}"

    validation = await valider_entree(sample)
    if not validation["valid"]:
        logger.warning(f"Upload blocked [{validation['type']}] — '{safe_name}'")
        await track("upload_blocked", detail=f"{safe_name} | {validation['type']}")
        return JSONResponse({"error": "Suspicious content. Upload rejected."}, status_code=400)

    destination = os.path.join(DATA_DIR, safe_name)
    existed_before = os.path.exists(destination)

    with open(destination, "wb") as out:
        out.write(content)

    reindex_warning = None
    changed = None
    try:
        # index_data est synchrone
        changed = bool(await asyncio.to_thread(index_data, force_reindex=False))
    except Exception as e:
        reindex_warning = str(e)
        logger.warning(f"Upload automatic reindexing failed: {e}")

    qdrant_points = _count_points_for_filename(safe_name)

    if existed_before:
        await track("replace", detail=f"{safe_name} | {len(content)//1024} KB (upsert)")
        logger.info(f"File replaced (upsert upload): {safe_name}")
        payload = {"message": f"'{safe_name}' replaced and indexed.", "filename": safe_name}
    else:
        await track("upload", detail=f"{safe_name} | {len(content)//1024} KB")
        logger.info(f"File uploaded: {safe_name}")
        payload = {"message": f"'{safe_name}' uploaded and indexed.", "filename": safe_name}

    payload["ingestion"] = {
        "changed": changed,
        "qdrant_points": qdrant_points,
        "verified": (qdrant_points is not None and qdrant_points > 0),
        "summary": (
            f"Ingestion {'updated' if changed else 'no changes detected'}; "
            + (f"Qdrant={qdrant_points} chunk(s)." if qdrant_points is not None else "Qdrant unverified.")
        ),
    }
    if reindex_warning:
        payload["warning"] = "File uploaded, but automatic reindexing failed."
    return payload


@admin_router.get("/api/file/{filename:path}")
async def serve_file(filename: str, request: Request, user_id: str = Depends(get_current_user)):
    """Serve a file from tenant storage for in-browser preview."""
    safe_name = _sanitize_filename(os.path.basename(filename))
    if not safe_name:
        return JSONResponse({"error": "Invalid filename."}, status_code=400)

    tenant_id = await get_tenant_id(user_id)

    # Look in tenant subdirectory first, then root DATA_DIR
    candidates = [
        os.path.join(DATA_DIR, tenant_id, safe_name),
        os.path.join(DATA_DIR, safe_name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            mime, _ = mimetypes.guess_type(safe_name)
            mime = mime or "application/octet-stream"
            # Force inline display for text/PDF; attachment otherwise
            if mime.startswith("text/") or mime == "application/pdf":
                headers = {"Content-Disposition": f'inline; filename="{safe_name}"'}
            else:
                headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}
            return FileResponse(path, media_type=mime, headers=headers)

    return JSONResponse({"error": "File not found."}, status_code=404)


@admin_router.get("/api/file-text/{filename:path}")
async def serve_file_text(filename: str, request: Request, user_id: str = Depends(get_current_user)):
    """Return the extracted plain text of a file (PDF → pypdf, others → raw read)."""
    safe_name = _sanitize_filename(os.path.basename(filename))
    if not safe_name:
        return JSONResponse({"error": "Invalid filename."}, status_code=400)

    tenant_id = await get_tenant_id(user_id)
    candidates = [
        os.path.join(DATA_DIR, tenant_id, safe_name),
        os.path.join(DATA_DIR, safe_name),
    ]
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if not path:
        return JSONResponse({"error": "File not found."}, status_code=404)

    try:
        ext = os.path.splitext(safe_name)[1].lower()
        if ext == ".pdf":
            from src.ingestion.parser import _parse_pdf_pypdf
            text = _parse_pdf_pypdf(path) or ""
        elif ext in (".docx", ".doc"):
            from src.ingestion.parser import _parse_docx
            text = _parse_docx(path) or ""
        elif ext == ".xlsx":
            from src.ingestion.parser import _xlsx_to_text
            text = _xlsx_to_text(path) or ""
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(text)
    except Exception as e:
        logger.error(f"file-text error for {safe_name}: {e}")
        return JSONResponse({"error": "Failed to extract text."}, status_code=500)


@admin_router.get("/api/file-xlsx/{filename:path}")
async def serve_file_xlsx(filename: str, request: Request, user_id: str = Depends(get_current_user)):
    """Return Excel file as structured JSON: [{sheet, headers, rows}]."""
    safe_name = _sanitize_filename(os.path.basename(filename))
    if not safe_name or not safe_name.lower().endswith(".xlsx"):
        return JSONResponse({"error": "Invalid file."}, status_code=400)
    tenant_id = await get_tenant_id(user_id)
    candidates = [os.path.join(DATA_DIR, tenant_id, safe_name), os.path.join(DATA_DIR, safe_name)]
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if not path:
        return JSONResponse({"error": "File not found."}, status_code=404)
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        sheets = []
        for name in wb.sheetnames:
            ws = wb[name]
            rows = [[str(c.value) if c.value is not None else "" for c in row] for row in ws.iter_rows()]
            if not rows:
                continue
            sheets.append({"sheet": name, "headers": rows[0], "rows": rows[1:]})
        wb.close()
        return JSONResponse(sheets)
    except Exception as e:
        logger.error(f"file-xlsx error for {safe_name}: {e}")
        return JSONResponse({"error": "Failed to read Excel file."}, status_code=500)


@admin_router.delete("/api/admin/delete")
async def admin_delete(request: Request):
    require_monitoring(request)
    body = await request.json()
    filename = (body or {}).get("filename", "").strip()

    # Path traversal protection
    if not filename or any(s in filename for s in ("/", "\\", "..")):
        return JSONResponse({"error": "Invalid filename"}, status_code=400)

    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return JSONResponse({"error": "File not found"}, status_code=404)

    os.remove(path)

    # Immediate deletion of Qdrant chunks linked to the file to guarantee consistency.
    try:
        from src.ingestion.vector_store import get_store, remove_files
        # get_store et remove_files sont synchrones
        store = get_store(force_reindex=False)
        await asyncio.to_thread(remove_files, store, {filename})
    except Exception as e:
        logger.warning(f"Immediate Qdrant delete failed: {e}")

    reindex_warning = None
    changed = None
    try:
        changed = bool(await asyncio.to_thread(index_data, force_reindex=False))
    except Exception as e:
        reindex_warning = str(e)
        logger.warning(f"Delete automatic reindexing failed: {e}")

    qdrant_points = _count_points_for_filename(filename)

    await track("reindex", detail=f"deletion: {filename}")
    logger.info(f"File deleted: {filename}")
    payload = {"message": f"'{filename}' deleted and index updated."}
    payload["ingestion"] = {
        "changed": changed,
        "qdrant_points": qdrant_points,
        "verified": (qdrant_points == 0) if qdrant_points is not None else False,
        "summary": (
            f"Ingestion {'updated' if changed else 'no changes detected'}; "
            + (f"Qdrant={qdrant_points} remaining chunk(s)." if qdrant_points is not None else "Qdrant unverified.")
        ),
    }
    if reindex_warning:
        payload["warning"] = "File deleted, but automatic reindexing failed."
    return payload
