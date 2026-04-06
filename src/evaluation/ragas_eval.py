"""RAGAS evaluation for RAG quality measurement.

Scores a single (question, contexts, answer) triple using three metrics:
- faithfulness       : is the answer grounded in the provided context?
- answer_relevancy   : does the answer address the question?
- context_precision  : are the retrieved passages relevant to the question?

Returns a dict with float scores in [0, 1] for each metric.
Falls back to a lightweight heuristic scorer if the ragas package is not
installed, so the endpoint never crashes in minimal deployments.
"""

import logging
import os
from typing import List

logger = logging.getLogger(__name__)


def _ragas_score(question: str, contexts: List[str], answer: str) -> dict:
    """Run RAGAS evaluation. Requires the ragas package and a configured LLM."""
    from datasets import Dataset  # type: ignore
    from ragas import evaluate  # type: ignore
    from ragas.metrics import faithfulness, answer_relevancy, context_precision  # type: ignore

    data = {
        "question": [question],
        "answer": [answer],
        "contexts": [contexts],
        # context_precision needs ground_truth; we use the answer as a proxy
        "ground_truth": [answer],
    }
    dataset = Dataset.from_dict(data)
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision])
    df = result.to_pandas()
    row = df.iloc[0]
    return {
        "faithfulness": round(float(row.get("faithfulness", 0.0)), 4),
        "answer_relevancy": round(float(row.get("answer_relevancy", 0.0)), 4),
        "context_precision": round(float(row.get("context_precision", 0.0)), 4),
    }


def _heuristic_score(question: str, contexts: List[str], answer: str) -> dict:
    """Lightweight fallback when ragas is not installed.

    Uses simple token-overlap heuristics — not a replacement for real RAGAS,
    but good enough to surface obvious quality problems.
    """
    def _tokens(text: str):
        return set(text.lower().split())

    q_tokens = _tokens(question)
    a_tokens = _tokens(answer)
    ctx_tokens = _tokens(" ".join(contexts))

    # faithfulness: fraction of answer tokens found in contexts
    overlap_ctx_ans = a_tokens & ctx_tokens
    faithfulness = len(overlap_ctx_ans) / max(len(a_tokens), 1)

    # answer_relevancy: fraction of question tokens addressed in answer
    overlap_q_ans = q_tokens & a_tokens
    answer_relevancy = len(overlap_q_ans) / max(len(q_tokens), 1)

    # context_precision: fraction of question tokens present in contexts
    overlap_q_ctx = q_tokens & ctx_tokens
    context_precision = len(overlap_q_ctx) / max(len(q_tokens), 1)

    return {
        "faithfulness": round(min(faithfulness, 1.0), 4),
        "answer_relevancy": round(min(answer_relevancy, 1.0), 4),
        "context_precision": round(min(context_precision, 1.0), 4),
        "_heuristic": True,  # flag so callers know this is the fallback
    }


def evaluate_rag(question: str, contexts: List[str], answer: str) -> dict:
    """Return RAGAS quality scores for a RAG response.

    Args:
        question: The user question.
        contexts: List of retrieved passage strings used to generate the answer.
        answer:   The generated answer to evaluate.

    Returns:
        Dict with keys faithfulness, answer_relevancy, context_precision (floats 0-1).
        If ragas is unavailable, also includes _heuristic=True.
    """
    try:
        scores = _ragas_score(question, contexts, answer)
        logger.info("RAGAS scores: %s", scores)
        return scores
    except ImportError:
        logger.warning("ragas package not installed — using heuristic fallback scorer.")
        return _heuristic_score(question, contexts, answer)
    except Exception as exc:
        logger.warning("RAGAS evaluation failed (%s) — using heuristic fallback.", exc)
        return _heuristic_score(question, contexts, answer)
