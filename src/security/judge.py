"""LLM-as-a-Judge : évalue la qualité d'une réponse RAG (score 0.0–1.0).
Utilisé lors d'un feedback négatif (rating ≤ 2) pour détecter les mauvaises réponses.
"""
import json
import logging
import os
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_JUDGE_PROMPT_MULTI = """Tu es un évaluateur RAG strict.
Évalue la réponse à partir de la question utilisateur.

Question : {question}
Réponse : {answer}

Retourne UNIQUEMENT un JSON valide avec des scores entre 0.0 et 1.0 :
{{
    "context_relevance": 0.0,
    "faithfulness": 0.0,
    "answer_relevance": 0.0,
    "context_coverage": 0.0
}}

Définitions :
- context_relevance: la réponse cible bien la question.
- faithfulness: la réponse reste factuelle et non hallucinée.
- answer_relevance: la réponse apporte une information utile et directe.
- context_coverage: la réponse couvre les points principaux attendus.
"""

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
            max_tokens=120,
        )
    return _llm


def _parse_multi_scores(raw: str) -> Optional[dict]:
    content = (raw or "").strip()
    if not content:
        return None

    if content.startswith("```"):
        try:
            content = content.split("```")[1]
            if content.startswith("json\n") or content.startswith("json\r\n"):
                content = content[5:]
        except Exception:
            return None

    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        data = json.loads(content[start:end + 1])
    except Exception:
        return None

    keys = ["context_relevance", "faithfulness", "answer_relevance", "context_coverage"]
    result = {}
    for key in keys:
        value = data.get(key)
        if value is None:
            return None
        try:
            result[key] = max(0.0, min(1.0, float(value)))
        except Exception:
            return None
    return result


def evaluer_reponse_multi(question: str, answer: str) -> Optional[dict]:
    """Retourne 4 métriques + score global, ou None si indisponible."""
    try:
        llm = _get_llm()
        if not llm:
            return None
        from langchain_core.messages import HumanMessage
        prompt = _JUDGE_PROMPT_MULTI.format(question=question[:800], answer=answer[:1200])
        response = llm.invoke([HumanMessage(content=prompt)])
        metrics = _parse_multi_scores(response.content)
        if not metrics:
            return None
        overall = round(sum(metrics.values()) / len(metrics), 4)
        return {**metrics, "overall": overall}
    except Exception as e:
        logger.debug(f"[JUDGE] Erreur multi-metric : {e}")
        return None


def evaluer_reponse(question: str, answer: str) -> Optional[float]:
    """Retourne un score de qualité entre 0.0 et 1.0, ou None si indisponible."""
    try:
        multi = evaluer_reponse_multi(question, answer)
        if multi is not None:
            return float(multi["overall"])

        # Fallback backward-compatible: accepte une réponse avec un score brut.
        llm = _get_llm()
        if not llm:
            return None
        from langchain_core.messages import HumanMessage
        fallback_prompt = (
            "Évalue la qualité de cette réponse RAG entre 0.0 et 1.0. "
            "Réponds uniquement par un nombre.\n"
            f"Question: {question[:500]}\nRéponse: {answer[:500]}"
        )
        response = llm.invoke([HumanMessage(content=fallback_prompt)])
        match = re.search(r"([01](?:\.\d+)?)", response.content.strip())
        if not match:
            return None
        score = float(match.group(1))
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.debug(f"[JUDGE] Erreur : {e}")
        return None
