"""LLM-as-a-Judge : évalue la qualité d'une réponse RAG (score 0.0–1.0).
Utilisé lors d'un feedback négatif (rating ≤ 2) pour détecter les mauvaises réponses.
"""
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """Tu es un évaluateur de qualité pour un assistant de lore de jeu.
Évalue si la réponse fournie est pertinente et correcte par rapport à la question.

Question : {question}
Réponse : {answer}

Réponds UNIQUEMENT avec un nombre décimal entre 0.0 et 1.0 :
- 1.0 = réponse parfaite, complète et pertinente
- 0.5 = réponse partielle ou approximative
- 0.0 = réponse incorrecte, hors sujet ou vide

Score :"""

_llm = None
_llm_lock = threading.Lock()


def _get_llm():
    global _llm
    if _llm is not None:
        return _llm
    with _llm_lock:
        if _llm is not None:
            return _llm
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "deepseek-chat"),
            base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=api_key,
            temperature=0,
            max_tokens=10,
        )
    return _llm


def evaluer_reponse(question: str, answer: str) -> Optional[float]:
    """Retourne un score de qualité entre 0.0 et 1.0, ou None si indisponible."""
    try:
        llm = _get_llm()
        if not llm:
            return None
        from langchain_core.messages import HumanMessage
        prompt = _JUDGE_PROMPT.format(question=question[:500], answer=answer[:500])
        response = llm.invoke([HumanMessage(content=prompt)])
        score = float(response.content.strip().split()[0])
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.debug(f"[JUDGE] Erreur : {e}")
        return None
