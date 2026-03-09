"""
Ce module donne une "voix" a notre systeme.
Il utilise LangChain pour communiquer avec le LLM (DeepSeek, Groq, OpenAI, etc.)
et genere des reponses basees uniquement sur le contexte fourni (approche RAG).

Le provider LLM est configurable via les variables d'environnement :
- LLM_BASE_URL : URL de l'API (defaut: DeepSeek)
- LLM_MODEL    : Nom du modele (defaut: deepseek-chat)
"""
import os
import logging
from typing import List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

# On s'assure que les variables d'environnement (.env) sont bien lues
load_dotenv()

# Configuration du LLM via variables d'environnement
_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
_model: str = os.getenv("LLM_MODEL", "deepseek-chat")

# On initialise le client LangChain une seule fois au chargement (singleton).
# Compatible avec DeepSeek, Groq, OpenAI, Ollama, et tout provider OpenAI-compatible.
_llm: Optional[ChatOpenAI] = ChatOpenAI(
    model=_model,
    base_url=_base_url,
    api_key=_api_key,
    temperature=0.2
) if _api_key else None


def generer_reponse(question: str, passages: List[str], sources: List[str] = None) -> str:
    """
    Le prompt "RAG" classique.
    On donne des instructions strictes a l'IA pour qu'elle ne se base QUE
    sur les morceaux de texte qu'on lui fournit, afin d'eviter les "hallucinations".
    """
    if not _llm:
        raise ValueError("Cle OPENAI_API_KEY manquante. Verifie ton fichier .env pour pouvoir utiliser l'IA.")

    # On colle tous les resultats trouves en un seul bloc de contexte
    contexte = "\n\n".join(passages)
    liste_sources = ", ".join(sources) if sources else "sources inconnues"

    # Construction des messages avec LangChain
    messages = [
        SystemMessage(content=(
            "Tu es un assistant specialise dans le lore du jeu Aethelgard Online. "
            "Reponds uniquement en te basant sur les informations du contexte fourni. "
            "N'invente absolument rien. Si l'information ne s'y trouve pas, dis-le honnetement. "
            f"(pour t'aider, les sources de ce contexte sont : {liste_sources}).\n\n"
            f"Voici ton contexte de reference :\n{contexte}"
        )),
        HumanMessage(content=question)
    ]

    # Appel au LLM via LangChain (fonctionne avec n'importe quel provider)
    response = _llm.invoke(messages)

    logger.info("L'IA a termine de rediger sa reponse.")

    return response.content.strip()
