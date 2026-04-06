"""ReAct agent — Thought / Action / Observation loop.
Utilise rechercher_passages comme unique outil et OpenRouter via httpx.
Zero PyTorch.
"""
import logging
import os
from typing import List

import httpx

from src.search.search import rechercher_passages

logger = logging.getLogger(__name__)

_AGENT_MODEL = os.getenv("REACT_AGENT_MODEL", "qwen/qwen-2.5-7b-instruct")
_AGENT_MAX_ITERATIONS = 3
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY", "")

REACT_SYSTEM = """Tu es un assistant expert en lore de jeu de role fantastique.
Tu dois TOUJOURS suivre ce format exactement:
Thought: [ta reflexion sur la question et ce que tu dois chercher]
Action: search_rag
Action Input: [la requete a passer a l'outil de recherche]
Observation: [les resultats de la recherche — tu les recevras]
... (repeter au plus 3 fois) ...
Final Answer: [ta reponse finale, basee sur les observations]

Si tu as suffisamment d'information, reponds directement avec Final Answer.
"""

REACT_USER = """Question: {question}

Commence par Thought:"""


def _call_agent_llm(prompt: str) -> str:
    """Appelle OpenRouter directement via httpx (no langchain, zero torch)."""
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://oracle-lorekeeper.local",
                    "X-Title": "Oracle-LoreKeeper ReAct Agent",
                },
                json={
                    "model": _AGENT_MODEL,
                    "messages": [
                        {"role": "system", "content": REACT_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Agent LLM call failed: {e}")
        return ""


def _invoke_search_rag(query: str) -> str:
    """Outil search_rag — appelle le pipeline RAG existant."""
    try:
        passages, sources, _ = rechercher_passages(query)
        parts: List[str] = []
        for i, (p, s) in enumerate(zip(passages, sources)):
            parts.append(f"Passage {i + 1} [source: {s}]:\n{p}")
        return "\n\n".join(parts) if parts else "Aucun passage trouve."
    except Exception as e:
        logger.warning(f"search_rag failed: {e}")
        return f"Erreur recherche: {e}"


def run_react_agent(question: str) -> dict:
    """Boucle ReAct: Thought -> Action -> Observation -> Final Answer.
    Retourne {answer, iterations, tool_calls, model}.
    """
    tool_calls: List[dict] = []
    prompt = REACT_USER.format(question=question)

    for iteration in range(1, _AGENT_MAX_ITERATIONS + 1):
        response = _call_agent_llm(prompt)
        if not response:
            break

        # Detecter Final Answer
        if "Final Answer:" in response:
            final = response.split("Final Answer:", 1)[1].strip()
            return {
                "answer": final,
                "iterations": iteration,
                "tool_calls": tool_calls,
                "model": _AGENT_MODEL,
                "raw": response,
            }

        # Detecter Action
        if "Action:" in response and "Action Input:" in response:
            action_line = response.split("Action:")[1].split("Action Input:")[0].strip()
            action_input = response.split("Action Input:")[1].strip()

            if action_line.strip().lower() == "search_rag":
                observation = _invoke_search_rag(action_input)
                tool_calls.append({"action": action_line, "input": action_input, "result_snippet": observation[:200]})
                prompt += "\n\n" + response + f"\n\nObservation: {observation}\n\nThought:"
            else:
                # Action non reconnue — on continue
                prompt += "\n\n" + response + "\n\nObservation: Action non reconnue. Utilise search_rag.\n\nThought:"
        else:
            # Pas d'action detectee — on traite comme une reponse directe
            return {
                "answer": response,
                "iterations": iteration,
                "tool_calls": tool_calls,
                "model": _AGENT_MODEL,
                "raw": response,
            }

    # Max iterations atteint — extraire ce qu'on a
    return {
        "answer": response.split("Final Answer:")[-1].strip() if "Final Answer:" in response else response,
        "iterations": _AGENT_MAX_ITERATIONS,
        "tool_calls": tool_calls,
        "model": _AGENT_MODEL,
        "raw": response,
    }
