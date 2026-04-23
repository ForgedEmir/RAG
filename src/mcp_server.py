"""
Serveur MCP (Model Context Protocol) pour Oracle LoreKeeper.
Expose le RAG d'Aethelgard Online comme outils MCP utilisables par Claude Desktop, Cursor, etc.

Transports :
  - stdio  (défaut) : Claude Desktop local
    - sse             : HTTP/SSE pour connexions distantes (Claude.ai web, Cursor, etc.)

Lancement stdio (Claude Desktop) :
    python mcp_server.py

Lancement SSE (serveur distant, port 8001 par défaut) :
    MCP_TRANSPORT=sse python mcp_server.py
    MCP_TRANSPORT=sse MCP_PORT=9000 python mcp_server.py

Configuration Claude Desktop (%APPDATA%\\Claude\\claude_desktop_config.json) :
    {
      "mcpServers": {
        "lorekeeper": {
          "command": "python",
          "args": ["C:/chemin/vers/Oracle-LoreKeeper/mcp_server.py"],
                    "env": { "LLM_API_KEY": "...", "QDRANT_URL": "...", "QDRANT_API_KEY": "..." }
        }
      }
    }

Configuration client SSE distant (Claude.ai / Cursor) :
    URL : http://<votre-serveur>:8001/sse
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

# Mode rapide pour MCP local: évite les composants les plus lents au premier appel.
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


# ── Lifespan : connexion Qdrant gérée proprement au démarrage/arrêt ──────────

@dataclass
class AppContext:
    qdrant: QdrantClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Ouvre la connexion Qdrant au démarrage, la ferme à l'arrêt."""
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
    passages: list[str] = Field(description="Passages bruts trouvés dans les archives")
    sources:  list[str] = Field(description="Fichiers sources consultés")
    total:    int       = Field(description="Nombre de passages trouvés")


class LogResult(BaseModel):
    path: str = Field(description="Chemin du fichier de log")
    lines: list[str] = Field(description="Dernieres lignes du log")
    total_lines: int = Field(description="Nombre total de lignes dans le fichier")


class FileListResult(BaseModel):
    root: str = Field(description="Racine de recherche resolue")
    files: list[str] = Field(description="Fichiers detectes")
    total: int = Field(description="Nombre de fichiers detectes")


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
        return None, f"Acces refuse: le chemin doit rester dans {_MCP_FILE_ROOT}"

    if not resolved.exists():
        return None, f"Chemin introuvable: {resolved}"

    if expect_dir and not resolved.is_dir():
        return None, f"Le chemin n'est pas un dossier: {resolved}"

    if not expect_dir and not resolved.is_file():
        return None, f"Le chemin n'est pas un fichier: {resolved}"

    return resolved, None


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def ask_lore(question: str, ctx: Context) -> str:
    """
    Pose une question sur le lore du jeu Aethelgard Online.
    L'Oracle consulte les archives et répond uniquement avec des faits réels.
    Ne répond pas s'il ne trouve pas l'information dans les documents indexés.

    Args:
        question: La question sur le lore (personnages, lieux, factions, artefacts, timeline...)
    """
    await ctx.info(f"Recherche dans les archives pour : {question!r}")
    try:
        from src.search.search import rechercher_passages
        from src.generation.generator import stream_reponse

        await ctx.report_progress(progress=0.3, total=1.0, message="Recherche vectorielle...")
        # rechercher_passages est maintenant asynchrone
        passages, sources, *_ = await rechercher_passages(question)

        if not passages:
            return "Je n'ai trouvé aucun passage pertinent dans les archives pour cette question."

        await ctx.report_progress(progress=0.7, total=1.0, message="Génération de la réponse...")
        # stream_reponse est maintenant asynchrone
        chunks: list[str] = []
        async for chunk in stream_reponse(question, passages, sources=sources, history=[]):
            chunks.append(chunk)
        reponse = "".join(chunks).strip()

        sources_str = ", ".join(sources) if sources else "sources inconnues"
        await ctx.report_progress(progress=1.0, total=1.0, message="Terminé.")
        return f"{reponse}\n\n---\n*Sources : {sources_str}*"
    except Exception as e:
        return f"Erreur lors de la consultation des archives : {e}"


@mcp.tool()
async def search_lore(query: str, ctx: Context) -> SearchResult:
    """
    Recherche les passages bruts dans les archives sans générer de réponse LLM.
    Retourne les documents exactement tels qu'ils sont stockés dans Qdrant.
    Utile pour voir la source primaire avant toute interprétation.

    Args:
        query: Le sujet à rechercher (nom d'un personnage, lieu, faction, artefact...)
    """
    await ctx.info(f"Recherche brute : {query!r}")
    try:
        from src.search.search import rechercher_passages
        # rechercher_passages est maintenant asynchrone
        passages, sources, conf_scores, _ = await rechercher_passages(query)
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
        return SearchResult(passages=[f"Erreur : {e}"], sources=[], total=0)


@mcp.tool()
async def list_save_files(folder_path: str = ".", ctx: Context = None) -> FileListResult:
    """Liste les fichiers de sauvegarde/log dans la sandbox MCP_FILE_ROOT."""
    if ctx:
        await ctx.info(f"Listing securise du dossier: {folder_path!r}")

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
    """Lit les dernieres lignes d'un fichier log texte, dans la sandbox MCP_FILE_ROOT."""
    await ctx.info(f"Lecture securisee du log: {file_path!r}")

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
        return LogResult(path=str(log_file), lines=[f"Erreur lecture: {e}"], total_lines=0)

    total = len(all_lines)
    lines = [line.rstrip("\n") for line in all_lines[-n:]]
    return LogResult(path=str(log_file), lines=lines, total_lines=total)


# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("lore://sources")
def list_sources() -> str:
    """Liste tous les fichiers lore actuellement indexés dans les archives."""
    try:
        from src.ingestion.run import list_current_files
        fichiers = list_current_files()
        if not fichiers:
            return "Aucun fichier indexé pour le moment."
        lines = "\n".join(f"- {f}" for f in sorted(fichiers.keys()))
        return f"{len(fichiers)} fichier(s) indexé(s) :\n\n{lines}"
    except Exception as e:
        return f"Erreur : {e}"


@mcp.resource("lore://stats")
def collection_stats() -> str:
    """Statistiques de la collection vectorielle Qdrant (nombre de vecteurs, état)."""
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
        return f"Collection : {_COLLECTION}\nVecteurs indexés : {count}\nStatut : {status}"
    except Exception as e:
        return f"Impossible de récupérer les stats : {e}"


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
