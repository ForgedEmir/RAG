"""
Génère les réponses de l'Oracle via un LLM (Groq, DeepSeek, etc.).
Bascule automatiquement sur le LLM de secours en cas d'erreur.
"""
import os
import logging
from typing import List, Optional, Iterator

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

logger = logging.getLogger(__name__)

_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
_primary_model: str = os.getenv("LLM_MODEL", "deepseek-chat")

_llm: Optional[ChatOpenAI] = ChatOpenAI(
    model=_primary_model,
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    api_key=_api_key,
    temperature=0.2,
) if _api_key else None

# LLM de secours (activé si FALLBACK_API_KEY est dans le .env)
_fallback_api_key: Optional[str] = os.getenv("FALLBACK_API_KEY")
_fallback_model: str = os.getenv("FALLBACK_MODEL", "llama-3.1-8b-instant")

_llm_fallback: Optional[ChatOpenAI] = ChatOpenAI(
    model=_fallback_model,
    base_url=os.getenv("FALLBACK_BASE_URL", "https://api.groq.com/openai/v1"),
    api_key=_fallback_api_key,
    temperature=0.2,
) if _fallback_api_key else None


def _build_messages(question: str, passages: List[str], sources: List[str], history: List[dict]) -> list:
    """Construit la conversation à envoyer au LLM (system + historique + question)."""
    contexte = "\n\n".join(passages)
    liste_sources = ", ".join(sources) if sources else "sources inconnues"

    messages = [
        SystemMessage(content=(
            "Tu es l'Oracle des Archives, gardien du lore du jeu Aethelgard Online. "
            "Réponds uniquement en te basant sur les informations du contexte ci-dessous. "
            "N'invente rien. Si l'information n'est pas dans le contexte, dis-le honnêtement. "
            "Rédige des réponses claires et bien structurées : utilise des paragraphes pour narrer, "
            "et des tirets (-) pour les listes si nécessaire. Évite les astérisques (*). "
            f"Sources : {liste_sources}\n\nContexte :\n{contexte}"
        ))
    ]

    # On injecte les 5 derniers échanges pour la mémoire conversationnelle
    for exchange in history[-5:]:
        messages.append(HumanMessage(content=exchange["question"]))
        messages.append(AIMessage(content=exchange["answer"]))

    messages.append(HumanMessage(content=question))
    return messages


def reformuler_question(question: str, history: List[dict]) -> str:
    """Reformule une question vague en version autonome grâce à l'historique.
    Ex: "il fait quelle taille ?" → "Quelle est la taille de Lucas le Tranchant ?"
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
        logger.warning(f"Reformulation échouée, on garde la question originale : {e}")
        return question


def generer_reponse(question: str, passages: List[str], sources: List[str] = None, history: List[dict] = None) -> str:
    """Génère une réponse complète (non streamée)."""
    if not _llm:
        raise ValueError("Clé OPENAI_API_KEY manquante dans le fichier .env")
    messages = _build_messages(question, passages, sources or [], history or [])
    response = _llm.invoke(messages)
    return response.content.strip()


def stream_reponse(question: str, passages: List[str], sources: List[str] = None, history: List[dict] = None, model_used: Optional[list] = None) -> Iterator[str]:
    """Génère la réponse token par token (streaming).
    Si le LLM principal plante, on bascule sur le fallback.
    `model_used` : liste mutable pour que l'appelant sache quel modèle a répondu.
    """
    if not _llm:
        raise ValueError("Clé OPENAI_API_KEY manquante dans le fichier .env")
    messages = _build_messages(question, passages, sources or [], history or [])

    if model_used is not None:
        model_used.append(_primary_model)

    try:
        for chunk in _llm.stream(messages):
            if chunk.content:
                yield chunk.content
    except Exception as e:
        if _llm_fallback:
            logger.warning(f"LLM principal KO ({e}), bascule sur {_fallback_model}")
            if model_used is not None:
                model_used[0] = f"{_fallback_model} [fallback]"
            try:
                from src.monitoring.tracker import track as _track
                _track("fallback", detail=f"{_primary_model} → {_fallback_model} | {str(e)[:100]}")
            except Exception:
                pass
            for chunk in _llm_fallback.stream(messages):
                if chunk.content:
                    yield chunk.content
        else:
            raise
