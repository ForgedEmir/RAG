import os
import sys
import json
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from mcp.server.fastmcp import FastMCP, Context
from qdrant_client import QdrantClient
from pydantic import BaseModel, Field
from src.search.search import rechercher_passages

logging.basicConfig(level=logging.INFO)

_QDRANT_URL     = os.getenv("QDRANT_URL")
_QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
_COLLECTION     = "lore"


# ── Lifespan ──────────────────────────────────────────────────────────────────

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


mcp = FastMCP("Oracle LoreKeeper — Aethelgard Online",
              lifespan=app_lifespan,
              host="0.0.0.0",
              port=8000)


# ── Structured Output ─────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    passages: list[str] = Field(description="Passages bruts trouvés dans les archives")
    sources:  list[str] = Field(description="Fichiers sources consultés")
    total:    int       = Field(description="Nombre de passages trouvés")


class SaveFileResult(BaseModel):
    path:    str       = Field(description="Chemin du fichier lu")
    content: dict | list | str = Field(description="Contenu parsé du fichier")
    format:  str       = Field(description="Format détecté : json, xml, txt")


class LogResult(BaseModel):
    path:  str       = Field(description="Chemin du fichier de log")
    lines: list[str] = Field(description="Dernières lignes du log")
    total_lines: int = Field(description="Nombre total de lignes lues")


# ── Tools Lore ────────────────────────────────────────────────────────────────

@mcp.tool()
async def ask_lore(question: str, ctx: Context) -> str:
    """
    Pose une question sur le lore du jeu Aethelgard Online.
    L'Oracle consulte les archives et répond uniquement avec des faits réels.
    Ne répond pas s'il ne trouve pas l'information dans les documents indexés.

    Args:
        question: La question sur le lore (personnages, lieux, factions, artefacts, timeline...)
    """
    print(question)
    await ctx.info(f"Recherche dans les archives pour : {question!r}")
    try:
        from src.search.search import rechercher_passages
        from src.generation.generator import generer_reponse

        await ctx.report_progress(progress=0.3, total=1.0, message="Recherche vectorielle...")
        passages, sources = rechercher_passages(question)

        if not passages:
            return "Je n'ai trouvé aucun passage pertinent dans les archives pour cette question."

        await ctx.report_progress(progress=0.7, total=1.0, message="Génération de la réponse...")
        reponse = generer_reponse(question, passages, sources, history=[])

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
        passages, sources = rechercher_passages(query)
        return SearchResult(passages=passages, sources=sources, total=len(passages))
    except Exception as e:
        return SearchResult(passages=[f"Erreur : {e}"], sources=[], total=0)


# ── Tools Génériques Jeux ─────────────────────────────────────────────────────

@mcp.tool()
async def read_save_file(file_path: str, ctx: Context) -> SaveFileResult:
    """
    Lit un fichier de sauvegarde de jeu (JSON, XML, TXT).
    Fonctionne avec n'importe quel jeu : Minecraft, RPG, strategy games, etc.
    Exemples : advancements Minecraft, saves Stardew Valley, configs, inventaires...

    Args:
        file_path: Chemin absolu vers le fichier de sauvegarde
    """
    await ctx.info(f"Lecture du fichier : {file_path!r}")
    try:
        path = Path(file_path)

        if not path.exists():
            return SaveFileResult(path=file_path, content=f"Fichier introuvable : {file_path}", format="error")

        if not path.is_file():
            return SaveFileResult(path=file_path, content=f"Le chemin n'est pas un fichier : {file_path}", format="error")

        ext = path.suffix.lower()

        # JSON
        if ext == ".json":
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = json.load(f)
            return SaveFileResult(path=file_path, content=content, format="json")

        # XML
        elif ext in (".xml", ".nbt"):
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            root = tree.getroot()

            def xml_to_dict(element):
                result = {"tag": element.tag, "attributes": element.attrib, "text": element.text}
                children = [xml_to_dict(child) for child in element]
                if children:
                    result["children"] = children
                return result

            return SaveFileResult(path=file_path, content=xml_to_dict(root), format="xml")

        # Fichiers texte et autres
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            # Limite à 5000 caractères pour éviter les fichiers trop lourds
            if len(content) > 5000:
                content = content[:5000] + f"\n... [tronqué, {len(content)} caractères au total]"
            return SaveFileResult(path=file_path, content=content, format="txt")

    except json.JSONDecodeError as e:
        return SaveFileResult(path=file_path, content=f"Erreur JSON : {e}", format="error")
    except Exception as e:
        return SaveFileResult(path=file_path, content=f"Erreur : {e}", format="error")


@mcp.tool()
async def read_log_file(file_path: str, ctx: Context, last_n_lines: int = 50) -> LogResult:
    """
    Lit les dernières lignes d'un fichier de log de jeu.
    Utile pour voir les événements récents, achievements débloqués, erreurs...
    Fonctionne avec n'importe quel jeu qui génère des logs texte.

    Args:
        file_path: Chemin absolu vers le fichier de log
        last_n_lines: Nombre de dernières lignes à lire (défaut : 50, max : 500)
    """
    await ctx.info(f"Lecture du log : {file_path!r} (dernières {last_n_lines} lignes)")
    try:
        path = Path(file_path)

        if not path.exists():
            return LogResult(path=file_path, lines=[f"Fichier introuvable : {file_path}"], total_lines=0)

        last_n_lines = min(last_n_lines, 500)  # Sécurité : max 500 lignes

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total = len(all_lines)
        lines = [l.rstrip("\n") for l in all_lines[-last_n_lines:]]
        return LogResult(path=file_path, lines=lines, total_lines=total)

    except Exception as e:
        return LogResult(path=file_path, lines=[f"Erreur : {e}"], total_lines=0)


@mcp.tool()
async def list_save_files(folder_path: str, ctx: Context) -> str:
    """
    Liste les fichiers de sauvegarde dans un dossier de jeu.
    Utile pour trouver quels fichiers sont disponibles avant de les lire.
    Fonctionne avec n'importe quel jeu.

    Args:
        folder_path: Chemin absolu vers le dossier de sauvegardes du jeu
    """
    await ctx.info(f"Listing du dossier : {folder_path!r}")
    try:
        path = Path(folder_path)

        if not path.exists():
            return f"Dossier introuvable : {folder_path}"

        if not path.is_dir():
            return f"Le chemin n'est pas un dossier : {folder_path}"

        extensions_jeux = {".json", ".xml", ".txt", ".log", ".sav", ".dat", ".cfg", ".ini", ".yaml", ".yml", ".nbt"}
        files = []

        for item in sorted(path.rglob("*")):
            if item.is_file() and item.suffix.lower() in extensions_jeux:
                size = item.stat().st_size
                size_str = f"{size}B" if size < 1024 else f"{size//1024}KB"
                files.append(f"- {item.relative_to(path)} ({size_str})")

        if not files:
            return f"Aucun fichier de sauvegarde trouvé dans : {folder_path}"

        return f"{len(files)} fichier(s) trouvé(s) dans {folder_path} :\n\n" + "\n".join(files[:100])

    except Exception as e:
        return f"Erreur : {e}"


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
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
