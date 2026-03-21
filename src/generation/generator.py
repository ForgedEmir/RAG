"""
Génère une réponse à partir du contexte trouvé dans les archives (RAG).
Utilise Groq (ou tout LLM OpenAI-compatible) — fonctionne avec n'importe quel fournisseur.
"""
import os
import logging
from typing import List, Optional, Iterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")

_llm: Optional[ChatOpenAI] = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "deepseek-chat"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    api_key=_api_key,
    temperature=0.2,
) if _api_key else None


def _build_messages(question: str, passages: List[str], sources: List[str], history: List[dict]) -> list:
    """Construit la liste de messages à envoyer au LLM (avec historique)."""
    contexte = "\n\n".join(passages)
    liste_sources = ", ".join(sources) if sources else "sources inconnues"

    messages = [
        SystemMessage(content=(
            "Tu es un assistant spécialisé dans le lore du jeu Aethelgard Online. "
            "Réponds uniquement en te basant sur les informations du contexte ci-dessous. "
            "N'invente rien. Si l'information n'est pas dans le contexte, dis-le honnêtement. "
            f"Sources : {liste_sources}\n\nContexte :\n{contexte}"
        ))
    ]

    # Injecter les 5 derniers échanges pour la mémoire conversationnelle
    for exchange in history[-5:]:
        messages.append(HumanMessage(content=exchange["question"]))
        messages.append(AIMessage(content=exchange["answer"]))

    messages.append(HumanMessage(content=question))
    return messages


def reformuler_question(question: str, history: List[dict]) -> str:
    """Reformule la question en version autonome en tenant compte de l'historique.
    Ex: "il fait quelle taille ?" → "Quelle est la taille de Lucas le Tranchant ?"
    Retourne la question originale si pas d'historique ou si le LLM est indisponible.
    """
    if not history or not _llm:
        return question

    historique = "\n".join(
        f"User: {e['question']}\nAssistant: {e['answer']}" for e in history[-5:]
    )
    prompt = [
        SystemMessage(content=(
            "Reformule la question de l'utilisateur en une question autonome et précise "
            "en utilisant le contexte de l'historique si nécessaire. "
            "Retourne uniquement la question reformulée, sans explication."
        )),
        HumanMessage(content=f"Historique :\n{historique}\n\nQuestion : {question}"),
    ]
    try:
        result = _llm.invoke(prompt)
        reformulated = result.content.strip()
        logger.info(f"Question reformulée : {reformulated!r}")
        return reformulated
    except Exception as e:
        logger.warning(f"Reformulation échouée, question originale utilisée : {e}")
        return question


def generer_reponse(question: str, passages: List[str], sources: List[str] = None, history: List[dict] = None) -> str:
    """Génère une réponse complète (non streamée)."""
    if not _llm:
        raise ValueError("Clé OPENAI_API_KEY manquante dans le fichier .env")
    messages = _build_messages(question, passages, sources or [], history or [])
    response = _llm.invoke(messages)
    logger.info("Réponse générée.")
    return response.content.strip()


def stream_reponse(question: str, passages: List[str], sources: List[str] = None, history: List[dict] = None) -> Iterator[str]:
    """Génère la réponse en streaming, token par token."""
    if not _llm:
        raise ValueError("Clé OPENAI_API_KEY manquante dans le fichier .env")
    messages = _build_messages(question, passages, sources or [], history or [])
    for chunk in _llm.stream(messages):
        if chunk.content:
            yield chunk.content
