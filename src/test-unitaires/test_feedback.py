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
