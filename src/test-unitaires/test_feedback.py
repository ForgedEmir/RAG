"""Tests unitaires — endpoint feedback upvote/downvote basé sur trace_id."""
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


@patch("src.api.routes.track")
@patch("langfuse.Langfuse")
@patch("src.api.routes.os.getenv")
def test_feedback_valide(mock_getenv, mock_langfuse_cls, mock_track):
    values = {
        "LANGFUSE_PUBLIC_KEY": "pk_test",
        "LANGFUSE_SECRET_KEY": "sk_test",
        "LANGFUSE_HOST": "https://cloud.langfuse.com",
    }
    mock_getenv.side_effect = lambda k, d=None: values.get(k, d)

    client = create_client()
    resp = client.post("/api/feedback", json={
        "trace_id": "trace-123",
        "value": 1,
        "comment": "Bonne réponse",
    })

    assert resp.status_code == 200
    assert "Feedback" in resp.json()["message"]
    mock_langfuse_cls.return_value.create_score.assert_called_once()
    mock_langfuse_cls.return_value.flush.assert_called_once()
    mock_track.assert_called_once()


def test_feedback_value_invalide():
    client = create_client()
    resp = client.post("/api/feedback", json={
        "trace_id": "trace-123",
        "value": 0,
    })
    assert resp.status_code == 400


@patch("src.api.routes.os.getenv", side_effect=lambda k, d=None: "" if "LANGFUSE_" in k else d)
def test_feedback_langfuse_non_configure(_mock_getenv):
    client = create_client()
    resp = client.post("/api/feedback", json={
        "trace_id": "trace-123",
        "value": -1,
    })
    assert resp.status_code == 500
