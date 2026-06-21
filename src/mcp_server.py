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
_COLLECTION     = "lore"
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


def _resolve_sandbox_path(user_path: str, *, expect_dir: bool = False) -> tuple[Optional[Path], Optional[str]]:
    """Resout user_path dans MCP_FILE_ROOT et bloque les acces hors sandbox."""
    raw = (user_path or "").strip()
    if not raw:
        candidate = _MCP_FILE_ROOT
    else:
        p = Path(raw)
        candidate = p if p.is_absolute() else (_MCP_FILE_ROOT / p)

    try:
        resolved = candidate.resolve()
    except Exception as e:
        return None, f"Chemin invalide: {e}"

    if not resolved.is_relative_to(_MCP_FILE_ROOT):
        return None, f"Access denied: path must stay within {_MCP_FILE_ROOT}"

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
async def list_save_files(folder_path: str = ".", ctx: Context = None) -> FileListResult:
    """List save/log files within the MCP_FILE_ROOT sandbox."""
    if ctx:
        await ctx.info(f"Secure folder listing: {folder_path!r}")

    folder, err = _resolve_sandbox_path(folder_path, expect_dir=True)
    if err:
        return FileListResult(root=str(_MCP_FILE_ROOT), files=[err], total=0)

    files: list[str] = []
    for item in sorted(folder.rglob("*")):
        if item.is_file() and item.suffix.lower() in _ALLOWED_SAVE_EXTENSIONS:
            rel = item.relative_to(_MCP_FILE_ROOT)
            size = item.stat().st_size
            size_str = f"{size}B" if size < 1024 else f"{size // 1024}KB"
            files.append(f"{rel} ({size_str})")

    return FileListResult(root=str(folder), files=files[:200], total=len(files))


@mcp.tool()
async def read_log_file(file_path: str, ctx: Context, last_n_lines: int = 50) -> LogResult:
    """Read the last lines of a text log file within the MCP_FILE_ROOT sandbox."""
    await ctx.info(f"Secure log read: {file_path!r}")

    log_file, err = _resolve_sandbox_path(file_path, expect_dir=False)
    if err:
        return LogResult(path=file_path, lines=[err], total_lines=0)

    if log_file.suffix.lower() not in _ALLOWED_LOG_EXTENSIONS:
        return LogResult(
            path=str(log_file),
            lines=[f"Extension non autorisee ({log_file.suffix}). Autorisees: {', '.join(sorted(_ALLOWED_LOG_EXTENSIONS))}"],
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
    """List all lore files currently indexed in the archives."""
    try:
        from src.ingestion.run import list_current_files
        files = list_current_files()
        if not files:
            return "No files indexed yet."
        lines = "\n".join(f"- {f}" for f in sorted(files.keys()))
        return f"{len(files)} file(s) indexed:\n\n{lines}"
    except Exception as e:
        return f"Error: {e}"


@mcp.resource("lore://stats")
def collection_stats() -> str:
    """Qdrant vector collection statistics (vector count, status)."""
    try:
        if _QDRANT_URL and _QDRANT_API_KEY:
            client = QdrantClient(url=_QDRANT_URL, api_key=_QDRANT_API_KEY)
        else:
            db_path = os.path.join(os.path.dirname(__file__), "ingestion", "qdrant_db")
            client = QdrantClient(path=db_path)

        info = client.get_collection(_COLLECTION)
        count = info.points_count or 0
        status = info.status.value if hasattr(info.status, "value") else str(info.status)
        client.close()
        return f"Collection: {_COLLECTION}\nIndexed vectors: {count}\nStatus: {status}"
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
