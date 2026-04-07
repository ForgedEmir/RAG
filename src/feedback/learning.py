"""Apprentissage léger depuis les feedbacks utilisateurs.

Ce module ne réentraîne pas le LLM. Il ajuste le classement des chunks RAG
en fonction des votes passés (utile/pas utile) pour des questions similaires.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Dict, List, Tuple

_BASE_DIR = os.path.dirname(__file__)
_STATE_PATH = os.path.normpath(
    os.path.join(_BASE_DIR, "..", "ingestion", "qdrant_db", "feedback_learning.json")
)

_LOCK = threading.Lock()
_STATE = None

_MAX_TRACES = int(os.getenv("FEEDBACK_MAX_TRACES", "3000"))
_MAX_FEEDBACK = int(os.getenv("FEEDBACK_MAX_EVENTS", "8000"))
_MIN_SIM = float(os.getenv("FEEDBACK_MIN_SIM", "0.12"))
_CHUNK_WEIGHT = float(os.getenv("FEEDBACK_CHUNK_WEIGHT", "1.2"))
_SOURCE_WEIGHT = float(os.getenv("FEEDBACK_SOURCE_WEIGHT", "0.8"))
_SAME_USER_MULT = float(os.getenv("FEEDBACK_SAME_USER_MULT", "1.4"))
_OTHER_USER_MULT = float(os.getenv("FEEDBACK_OTHER_USER_MULT", "0.6"))
_WINDOW_DAYS = int(os.getenv("FEEDBACK_WINDOW_DAYS", "30"))
_MIN_TOKEN_LEN = int(os.getenv("FEEDBACK_MIN_TOKEN_LEN", "3"))
_TOKEN_RE = re.compile(r"[a-zA-Zà-ÿ0-9]+")


def _now_ts() -> int:
    return int(time.time())


def _default_state() -> dict:
    return {"traces": {}, "feedback": []}


def _ensure_parent_dir() -> None:
    os.makedirs(os.path.dirname(_STATE_PATH), exist_ok=True)


def _load_state() -> dict:
    global _STATE
    if _STATE is not None:
        return _STATE
    if not os.path.exists(_STATE_PATH):
        _STATE = _default_state()
        return _STATE
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "traces" in data and "feedback" in data:
                _STATE = data
            else:
                _STATE = _default_state()
    except Exception:
        _STATE = _default_state()
    return _STATE


def _save_state(state: dict) -> None:
    _ensure_parent_dir()
    with open(_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)


def _tokenize(text: str) -> set:
    words = _TOKEN_RE.findall((text or "").lower())
    return {w for w in words if len(w) >= _MIN_TOKEN_LEN}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / max(len(a | b), 1)


def _trim_state(state: dict) -> None:
    traces = state.get("traces", {})
    if len(traces) > _MAX_TRACES:
        items = sorted(traces.items(), key=lambda kv: kv[1].get("ts", 0), reverse=True)
        state["traces"] = dict(items[:_MAX_TRACES])

    feedback = state.get("feedback", [])
    if len(feedback) > _MAX_FEEDBACK:
        state["feedback"] = feedback[-_MAX_FEEDBACK:]


def register_trace_context(
    trace_id: str,
    user_id: str,
    question: str,
    passages: List[str],
    sources: List[str],
    chunk_ids: List[str],
) -> None:
    if not trace_id:
        return
    record = {
        "uid": user_id or "",
        "question": (question or "").strip()[:500],
        "passages": [(p or "")[:500] for p in (passages or [])][:5],
        "sources": list(dict.fromkeys((sources or [])[:10])),
        "chunks": list(dict.fromkeys((chunk_ids or [])[:20])),
        "ts": _now_ts(),
    }
    with _LOCK:
        state = _load_state()
        state["traces"][trace_id] = record
        _trim_state(state)
        _save_state(state)


def record_feedback_event(
    trace_id: str,
    user_id: str,
    value: int,
    question: str | None = None,
    message: str | None = None,
) -> dict:
    with _LOCK:
        state = _load_state()
        trace_data = state.get("traces", {}).get(trace_id, {})
        feedback_row = {
            "trace_id": trace_id,
            "uid": user_id or "",
            "value": 1 if value >= 1 else -1,
            "question": ((question or "").strip()[:500] or trace_data.get("question") or ""),
            "message": ((message or "").strip()[:500]),
            "sources": trace_data.get("sources", []),
            "chunks": trace_data.get("chunks", []),
            "ts": _now_ts(),
        }
        state.setdefault("feedback", []).append(feedback_row)
        _trim_state(state)
        _save_state(state)
        return {
            "matched_trace": bool(trace_data),
            "sources_count": len(feedback_row.get("sources", [])),
            "chunks_count": len(feedback_row.get("chunks", [])),
        }


def rerank_documents_with_feedback(question: str, user_id: str, docs: List[dict]) -> Tuple[List[dict], dict]:
    if not docs or not question:
        return docs, {"matched_feedbacks": 0, "adjusted_docs": 0}

    with _LOCK:
        state = _load_state()
        feedback_rows = list(state.get("feedback", []))

    q_tokens = _tokenize(question)
    if not q_tokens:
        return docs, {"matched_feedbacks": 0, "adjusted_docs": 0}

    now_ts = _now_ts()
    window_min_ts = now_ts - (_WINDOW_DAYS * 86400)
    source_scores: Dict[str, float] = {}
    chunk_scores: Dict[str, float] = {}
    matched_feedbacks = 0

    for row in feedback_rows:
        if row.get("ts", 0) < window_min_ts:
            continue
        fb_question = row.get("question", "")
        sim = _jaccard(q_tokens, _tokenize(fb_question))
        if sim < _MIN_SIM:
            continue

        matched_feedbacks += 1
        val = 1.0 if int(row.get("value", 0)) >= 1 else -1.0
        mult = _SAME_USER_MULT if (user_id and row.get("uid") == user_id) else _OTHER_USER_MULT
        weight = sim * val * mult

        for src in row.get("sources", []) or []:
            source_scores[src] = source_scores.get(src, 0.0) + (weight * _SOURCE_WEIGHT)
        for chunk_id in row.get("chunks", []) or []:
            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0.0) + (weight * _CHUNK_WEIGHT)

    if not source_scores and not chunk_scores:
        return docs, {"matched_feedbacks": matched_feedbacks, "adjusted_docs": 0}

    scored = []
    adjusted_docs = 0
    total = len(docs)
    for idx, doc in enumerate(docs):
        base = (total - idx) * 0.001
        src = doc.get("fichier", "inconnu")
        cid = doc.get("id", "")
        delta = source_scores.get(src, 0.0) + chunk_scores.get(cid, 0.0)
        if abs(delta) > 1e-9:
            adjusted_docs += 1
        scored.append((base + delta, idx, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, _, d in scored], {
        "matched_feedbacks": matched_feedbacks,
        "adjusted_docs": adjusted_docs,
    }
