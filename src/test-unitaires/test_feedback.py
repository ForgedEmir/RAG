"""Tests unitaires — Human-in-the-Loop Feedback endpoint."""
import pytest
from collections import deque
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from src.api.auth import get_current_user
from src.api.limiter import limiter, rate_limit_handler
from src.api.routes import register_routes


def _run_inline(fn, *args, **kwargs):
    fn(*args, **kwargs)
    return None


def create_client(user_id: str = "user-test-123") -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.dependency_overrides[get_current_user] = lambda: user_id
    register_routes(app, deque(maxlen=100))
    return TestClient(app)


@patch("src.monitoring.tracker._get_client", return_value=None)
def test_feedback_rating_valide(mock_sb):
    resp = create_client().post("/api/feedback", json={
        "session_id": "sess-001",
        "rating": 5,
        "comment": "Excellente réponse !",
    })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_feedback_rating_invalide():
    resp = create_client().post("/api/feedback", json={
        "session_id": "sess-001",
        "rating": 6,
    })
    assert resp.status_code == 400


@patch("src.monitoring.tracker._get_client", return_value=None)
@patch("src.monitoring.tracker.get_history", return_value=[{"question": "Q?", "answer": "R."}])
@patch("src.security.judge.evaluer_reponse", return_value=0.3)
@patch("src.monitoring.tracker.track")
def test_feedback_mauvaise_note_declenche_judge(mock_track, mock_judge, mock_history, mock_sb):
    """Rating ≤ 2 doit déclencher judge.py et tracker un flag si score < 0.5."""
    resp = create_client().post("/api/feedback", json={
        "session_id": "sess-002",
        "rating": 1,
        "comment": "Mauvaise réponse",
    })
    assert resp.status_code == 200


def test_feedback_vote_value_invalide():
    resp = create_client().post("/api/feedback/vote", json={
        "trace_id": "trace-001",
        "value": 0,
    })
    assert resp.status_code == 400


@patch("src.api.routes._executor.submit", side_effect=_run_inline)
@patch("src.api.routes.record_feedback_event")
@patch("src.monitoring.tracker._get_client", return_value=None)
@patch("src.api.routes.get_trace_context")
def test_feedback_vote_positif_trace_context(mock_trace_context, mock_sb, mock_record, mock_submit):
    mock_trace_context.return_value = {
        "trace_id": "trace-abc",
        "session_id": "3d8e0e6f-ff67-4c73-9f53-e546d3d60d44",
        "question": "Qui est Lucas ?",
        "answer": "Lucas est un chevalier.",
    }

    resp = create_client().post("/api/feedback/vote", json={
        "trace_id": "trace-abc",
        "value": 1,
    })

    assert resp.status_code == 200
    kwargs = mock_record.call_args.kwargs
    assert kwargs["source"] == "vote"
    assert kwargs["value"] == 1
    assert kwargs["rating"] == 5
    assert kwargs["trace_id"] == "trace-abc"
    assert kwargs["question"] == "Qui est Lucas ?"


@patch("src.api.routes._executor.submit", side_effect=_run_inline)
@patch("src.api.routes.record_feedback_event")
@patch("src.api.routes._evaluate_feedback_quality", return_value=(0.3, None))
@patch("src.monitoring.tracker._get_client", return_value=None)
def test_feedback_vote_negatif_declenche_judge(mock_sb, mock_eval, mock_record, mock_submit):
    resp = create_client().post("/api/feedback/vote", json={
        "trace_id": "trace-down",
        "value": -1,
        "session_id": "a859a0f8-4537-4135-a296-90a76ca846f4",
        "question": "Question test",
        "answer": "Réponse test",
    })

    assert resp.status_code == 200
    mock_eval.assert_called_once_with("Question test", "Réponse test")
    kwargs = mock_record.call_args.kwargs
    assert kwargs["source"] == "vote"
    assert kwargs["rating"] == 1
    assert kwargs["judge_score"] == 0.3
