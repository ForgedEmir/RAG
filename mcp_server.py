"""
Serveur MCP (Model Context Protocol) pour Oracle LoreKeeper.
Expose le RAG d'Aethelgard Online comme outils MCP utilisables par Claude Desktop, Cursor, etc.

Transports :
  - stdio  (défaut) : Claude Desktop local
  - sse             : HTTP/SSE pour connexions distantes (Claude.ai web, Cursor, CI...)

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
          "env": { "OPENAI_API_KEY": "...", "QDRANT_URL": "...", "QDRANT_API_KEY": "..." }
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

from dotenv import load_dotenv
load_dotenv()

# Mode rapide pour MCP local: évite les composants les plus lents au premier appel.
_MCP_FAST_MODE = os.getenv("MCP_FAST_MODE", "true").lower() != "false"
if _MCP_FAST_MODE:
    os.environ.setdefault("RERANKER_ENABLED", "false")
    os.environ.setdefault("QUERY_EXPANSION_ENABLED", "false")

sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP, Context
from qdrant_client import QdrantClient
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.WARNING)

_QDRANT_URL     = os.getenv("QDRANT_URL")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
_COLLECTION     = "lore"


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
        db_path = os.path.join(os.path.dirname(__file__), "src", "ingestion", "qdrant_db")
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
        passages, sources = rechercher_passages(question)

        if not passages:
            return "Je n'ai trouvé aucun passage pertinent dans les archives pour cette question."

        await ctx.report_progress(progress=0.7, total=1.0, message="Génération de la réponse...")
        # stream_reponse intègre déjà le fallback LLM en cas de 429/erreur provider.
        chunks: list[str] = []
        for chunk in stream_reponse(question, passages, sources=sources, history=[]):
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
        passages, sources = rechercher_passages(query)
        return SearchResult(passages=passages, sources=sources, total=len(passages))
    except Exception as e:
        return SearchResult(passages=[f"Erreur : {e}"], sources=[], total=0)


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
            db_path = os.path.join(os.path.dirname(__file__), "src", "ingestion", "qdrant_db")
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
