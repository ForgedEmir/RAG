"""
MCP (Model Context Protocol) server for Oracle LoreKeeper.
Exposes the Aethelgard Online RAG as MCP tools usable by Claude Desktop, Cursor, etc.

Transports:
  - stdio (default): local Claude Desktop
  - sse: HTTP/SSE for remote connections (Claude.ai web, Cursor, etc.)

stdio launch (Claude Desktop):
    python mcp_server.py

SSE launch (remote server, default port 8001):
    MCP_TRANSPORT=sse python mcp_server.py
    MCP_TRANSPORT=sse MCP_PORT=9000 python mcp_server.py

Claude Desktop config (%APPDATA%\\Claude\\claude_desktop_config.json):
    {
      "mcpServers": {
        "lorekeeper": {
          "command": "python",
          "args": ["C:/path/to/Oracle-LoreKeeper/mcp_server.py"],
                    "env": { "LLM_API_KEY": "...", "QDRANT_URL": "...", "QDRANT_API_KEY": "..." }
        }
      }
    }

Remote SSE client config (Claude.ai / Cursor):
    URL: http://<your-server>:8001/sse
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
from src.config.features import apply_feature_profile, env_bool

load_dotenv()

# Fast mode for local MCP: skips the slowest components on first call.
_MCP_FAST_MODE = env_bool("MCP_FAST_MODE", True)
if _MCP_FAST_MODE:
    os.environ.setdefault("RAG_FAST_MODE", "true")
apply_feature_profile()

# Point to project root so 'from src.xxx' imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp.server.fastmcp import FastMCP, Context
from qdrant_client import QdrantClient
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.WARNING)

_QDRANT_URL     = os.getenv("QDRANT_URL")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
# WHY: removed hardcoded _COLLECTION="lore" — the actual collection name is
# env-configurable (QDRANT_COLLECTION, default "documents_chunks") and is
# imported from src.ingestion.vector_store._COLLECTION_NAME where needed.
_MCP_FILE_ROOT  = Path(os.getenv("MCP_FILE_ROOT", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sample"))).resolve()
_ALLOWED_LOG_EXTENSIONS = {".log", ".txt", ".out"}
_ALLOWED_SAVE_EXTENSIONS = {".json", ".xml", ".txt", ".log", ".sav", ".dat", ".cfg", ".ini", ".yaml", ".yml", ".nbt"}

# WHY: When the MCP server is deployed as a per-tenant instance (one process per
# client), the tenant_id is set in the environment and tools don't need to
# expose it. When deployed as a shared instance, the agent must pass tenant_id
# explicitly. The tool signature accepts tenant_id as an optional argument with
# env-var fallback, so both modes work.
_DEFAULT_TENANT_ID = os.getenv("MCP_TENANT_ID", "")


# ── Lifespan: Qdrant connection managed cleanly at startup/shutdown ──────────

@dataclass
class AppContext:
    qdrant: QdrantClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Opens the Qdrant connection at startup and closes it on shutdown."""
    if _QDRANT_URL and _QDRANT_API_KEY:
        client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY)
    else:
        db_path = os.path.join(os.path.dirname(__file__), "ingestion", "qdrant_db")
        client = QdrantClient(path=db_path)
    try:
        yield AppContext(qdrant=client)
    finally:
        client.close()


mcp = FastMCP("Oracle LoreKeeper — Aethelgard Online", lifespan=app_lifespan)


# ── Structured Output ─────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    passages: list[str] = Field(description="Raw passages found in the archives")
    sources:  list[str] = Field(description="Source files consulted")
    total:    int       = Field(description="Number of passages found")


class LogResult(BaseModel):
    path: str = Field(description="Path to the log file")
    lines: list[str] = Field(description="Last lines of the log")
    total_lines: int = Field(description="Total number of lines in the file")


class FileListResult(BaseModel):
    root: str = Field(description="Resolved search root")
    files: list[str] = Field(description="Detected files")
    total: int = Field(description="Number of files detected")


def _resolve_sandbox_path(user_path: str, *, expect_dir: bool = False, tenant_id: str = "") -> tuple[Optional[Path], Optional[str]]:
    """Resolve user_path within the tenant-scoped sandbox.

    WHY (T1 leak): previously the sandbox was the global _MCP_FILE_ROOT, so
    any tenant sharing one MCP server could list and read every other tenant's
    files. Now the sandbox is _MCP_FILE_ROOT / <tenant_id> when tenant_id is
    set, falling back to _MCP_FILE_ROOT (global) when empty (single-tenant
    mode or admin).

    Path traversal is blocked by checking that the resolved path stays within
    the tenant sandbox.
    """
    # Determine the sandbox root: tenant subdirectory if tenant_id is set, else global root.
    if tenant_id:
        # WHY: prevent tenant_id path traversal (e.g. tenant_id="../other_tenant")
        if any(s in tenant_id for s in ("/", "\\", "..")):
            return None, "Invalid tenant_id"
        sandbox_root = (_MCP_FILE_ROOT / tenant_id).resolve()
    else:
        sandbox_root = _MCP_FILE_ROOT

    raw = (user_path or "").strip()
    if not raw:
        candidate = sandbox_root
    else:
        p = Path(raw)
        candidate = p if p.is_absolute() else (sandbox_root / p)

    try:
        resolved = candidate.resolve()
    except Exception as e:
        return None, f"Invalid path: {e}"

    if not resolved.is_relative_to(sandbox_root):
        return None, f"Access denied: path must stay within {sandbox_root}"

    if not resolved.exists():
        return None, f"Path not found: {resolved}"

    if expect_dir and not resolved.is_dir():
        return None, f"Path is not a directory: {resolved}"

    if not expect_dir and not resolved.is_file():
        return None, f"Path is not a file: {resolved}"

    return resolved, None


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def ask_lore(question: str, ctx: Context, tenant_id: str = "") -> str:
    """
    Ask a question about the lore of the Aethelgard Online game.
    The Oracle consults the archives and answers only with verified facts.
    Returns nothing if the information is not found in the indexed documents.

    Args:
        question: The lore question (characters, locations, factions, artifacts, timeline...)
        tenant_id: Optional tenant scope for multi-tenant deployments.
                   If omitted, falls back to the MCP_TENANT_ID env var.
                   Use empty string for the default/global tenant.
    """
    # WHY: Resolve the effective tenant_id once — env var fallback enables
    # per-tenant MCP deployments where the agent never has to know the tenant.
    effective_tenant = tenant_id or _DEFAULT_TENANT_ID
    await ctx.info(f"Searching the archives (tenant={effective_tenant or 'default'}) for: {question!r}")
    try:
        from src.search.search import search_passages
        from src.generation.generator import stream_response

        await ctx.report_progress(progress=0.3, total=1.0, message="Vector search...")
        # search_passages est maintenant asynchrone
        passages, sources, *_ = await search_passages(question, tenant_id=effective_tenant)

        if not passages:
            return "No relevant passages found in the archives for this question."

        await ctx.report_progress(progress=0.7, total=1.0, message="Generating response...")
        # stream_response est maintenant asynchrone
        chunks: list[str] = []
        async for chunk in stream_response(question, passages, sources=sources, history=[]):
            chunks.append(chunk)
        response = "".join(chunks).strip()

        sources_str = ", ".join(sources) if sources else "unknown sources"
        await ctx.report_progress(progress=1.0, total=1.0, message="Done.")
        return f"{response}\n\n---\n*Sources: {sources_str}*"
    except Exception as e:
        return f"Error consulting the archives: {e}"


@mcp.tool()
async def search_lore(query: str, ctx: Context, tenant_id: str = "") -> SearchResult:
    """
    Search raw passages in the archives without generating an LLM response.
    Returns documents exactly as stored in Qdrant.
    Useful for viewing primary sources before any interpretation.

    Args:
        query: The subject to search for (character name, location, faction, artifact...)
        tenant_id: Optional tenant scope for multi-tenant deployments.
                   If omitted, falls back to the MCP_TENANT_ID env var.
                   Use empty string for the default/global tenant.
    """
    effective_tenant = tenant_id or _DEFAULT_TENANT_ID
    await ctx.info(f"Raw search (tenant={effective_tenant or 'default'}): {query!r}")
    try:
        from src.search.search import search_passages
        # search_passages est maintenant asynchrone
        passages, sources, conf_scores, _ = await search_passages(query, tenant_id=effective_tenant)
        annotated = []
        for passage, score in zip(passages, conf_scores):
            if score >= 0.7:
                label = "🟢 HIGH"
            elif score >= 0.4:
                label = "🟡 MEDIUM"
            else:
                label = "🔴 LOW"
            annotated.append(f"[{label}] {passage}")
        return SearchResult(passages=annotated, sources=sources, total=len(passages))
    except Exception as e:
        return SearchResult(passages=[f"Error: {e}"], sources=[], total=0)


@mcp.tool()
async def list_save_files(folder_path: str = ".", ctx: Context = None,
                          tenant_id: str = "") -> FileListResult:
    """List save/log files within the tenant-scoped sandbox.

    Args:
        folder_path: Subfolder to list (relative to the tenant sandbox root).
        tenant_id: Optional tenant scope. Falls back to MCP_TENANT_ID env var.
                   CRITICAL: when omitted in a multi-tenant deployment, files
                   from every tenant may be visible. Always pass the caller's
                   tenant_id in shared MCP deployments.
    """
    effective_tenant = tenant_id or _DEFAULT_TENANT_ID
    if ctx:
        await ctx.info(f"Secure folder listing (tenant={effective_tenant or 'default'}): {folder_path!r}")

    folder, err = _resolve_sandbox_path(folder_path, expect_dir=True, tenant_id=effective_tenant)
    if err:
        return FileListResult(root=str(_MCP_FILE_ROOT), files=[err], total=0)

    # Sandbox root for relative path display
    sandbox_root = (_MCP_FILE_ROOT / effective_tenant) if effective_tenant else _MCP_FILE_ROOT
    files: list[str] = []
    for item in sorted(folder.rglob("*")):
        if item.is_file() and item.suffix.lower() in _ALLOWED_SAVE_EXTENSIONS:
            rel = item.relative_to(sandbox_root)
            size = item.stat().st_size
            size_str = f"{size}B" if size < 1024 else f"{size // 1024}KB"
            files.append(f"{rel} ({size_str})")

    return FileListResult(root=str(folder), files=files[:200], total=len(files))


@mcp.tool()
async def read_log_file(file_path: str, ctx: Context, last_n_lines: int = 50,
                        tenant_id: str = "") -> LogResult:
    """Read the last lines of a text log file within the tenant-scoped sandbox.

    Args:
        file_path: Path to the log file (relative to the tenant sandbox root).
        last_n_lines: Number of last lines to return (capped at 500).
        tenant_id: Optional tenant scope. Falls back to MCP_TENANT_ID env var.
                   CRITICAL: when omitted in a multi-tenant deployment, any
                   tenant's log file may be readable. Always pass the caller's
                   tenant_id in shared MCP deployments.
    """
    effective_tenant = tenant_id or _DEFAULT_TENANT_ID
    await ctx.info(f"Secure log read (tenant={effective_tenant or 'default'}): {file_path!r}")

    log_file, err = _resolve_sandbox_path(file_path, expect_dir=False, tenant_id=effective_tenant)
    if err:
        return LogResult(path=file_path, lines=[err], total_lines=0)

    if log_file.suffix.lower() not in _ALLOWED_LOG_EXTENSIONS:
        return LogResult(
            path=str(log_file),
            lines=[f"Extension not allowed ({log_file.suffix}). Allowed: {', '.join(sorted(_ALLOWED_LOG_EXTENSIONS))}"],
            total_lines=0,
        )

    n = max(1, min(int(last_n_lines), 500))
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
    except Exception as e:
        return LogResult(path=str(log_file), lines=[f"Read error: {e}"], total_lines=0)

    total = len(all_lines)
    lines = [line.rstrip("\n") for line in all_lines[-n:]]
    return LogResult(path=str(log_file), lines=lines, total_lines=total)


# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("lore://sources")
def list_sources() -> str:
    """List lore files indexed for the MCP_TENANT_ID tenant.

    WHY (T2 leak): previously called list_current_files() without tenant_id,
    leaking every tenant's filenames. Now scoped to _DEFAULT_TENANT_ID (set
    via MCP_TENANT_ID env var). MCP resources cannot accept parameters, so
    the tenant MUST be configured at deployment time.

    In single-tenant mode (MCP_TENANT_ID empty), lists all files.
    """
    try:
        from src.ingestion.run import list_current_files
        # WHY: scope the file scan to the configured tenant's subdirectory.
        files = list_current_files(tenant_id=_DEFAULT_TENANT_ID)
        if not files:
            return f"No files indexed for tenant='{_DEFAULT_TENANT_ID or 'default'}'."
        lines = "\n".join(f"- {f}" for f in sorted(files.keys()))
        return f"{len(files)} file(s) indexed for tenant='{_DEFAULT_TENANT_ID or 'default'}':\n\n{lines}"
    except Exception as e:
        return f"Error: {e}"


@mcp.resource("lore://stats")
def collection_stats() -> str:
    """Qdrant vector collection statistics, scoped to MCP_TENANT_ID.

    WHY (T2 leak): previously returned the total point count for the entire
    collection, leaking the total document volume of every tenant. Now counts
    only points tagged with _DEFAULT_TENANT_ID. In single-tenant mode, returns
    the total count.
    """
    try:
        if _QDRANT_URL and _QDRANT_API_KEY:
            client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY)
        else:
            db_path = os.path.join(os.path.dirname(__file__), "ingestion", "qdrant_db")
            client = QdrantClient(path=db_path)

        # WHY: count only points matching the configured tenant_id when set.
        if _DEFAULT_TENANT_ID:
            from qdrant_client.http import Filter, FieldCondition, MatchValue
            from src.ingestion.vector_store import _COLLECTION_NAME
            count_result = client.count(
                collection_name=_COLLECTION_NAME,
                count_filter=Filter(must=[
                    FieldCondition(key="metadata.tenant_id", match=MatchValue(value=_DEFAULT_TENANT_ID))
                ]),
                exact=True,
            )
            count = count_result.count
            label = f"tenant='{_DEFAULT_TENANT_ID}'"
        else:
            from src.ingestion.vector_store import _COLLECTION_NAME
            info = client.get_collection(_COLLECTION_NAME)
            count = info.points_count or 0
            label = "all tenants"

        status = "ok"
        client.close()
        return f"Collection: {_COLLECTION_NAME}\nTenant: {label}\nIndexed vectors: {count}\nStatus: {status}"
    except Exception as e:
        return f"Unable to retrieve stats: {e}"


def main():
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "8001"))
        # MCP 1.26.x: host/port are configured via settings, not run() kwargs.
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
