"""Tests unitaires — Flux d'authentification GitHub OAuth + /api/auth/me."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    from main import app
    return TestClient(app)


def test_auth_me_avec_jwt_valide(app_client):
    """/api/auth/me doit retourner le user_id si le JWT Supabase est valide."""
    with patch("src.api.auth._verify_supabase_jwt", return_value="user-uuid-123"):
        resp = app_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer fake-valid-token"},
        )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "user-uuid-123"


def test_auth_me_sans_token_dev_mode(app_client):
    """/api/auth/me en mode dev doit accepter le header x-local-guest-id."""
    with patch.dict("os.environ", {
        "APP_ENV": "development",
        "ALLOW_LOCAL_GUEST_HEADER": "true",
        "ALLOW_GUEST_MODE": "true",
    }):
        resp = app_client.get(
            "/api/auth/me",
            headers={"x-local-guest-id": "guest_abc123"},
        )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "guest_abc123"


def test_auth_me_token_invalide(app_client):
    """/api/auth/me doit retourner 401 si le JWT est invalide."""
    with patch("src.api.auth._verify_supabase_jwt", return_value=None):
        resp = app_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert resp.status_code == 401


def test_auth_me_sans_token_prod_mode(app_client):
    """/api/auth/me sans token en mode production doit retourner 401."""
    with patch.dict("os.environ", {"APP_ENV": "production"}):
        resp = app_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_guest_mode_efface_apres_oauth():
    """Guest logic must be cleared if an OAuth session is detected."""
    # This test checks the JS logic (frontend side) - simulated via /api/auth/config API
    # et on s'assure que le header Authorization prend le dessus sur x-local-guest-id
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    with patch("src.api.auth._verify_supabase_jwt", return_value="oauth-user-github-999"):
        resp = client.get(
            "/api/auth/me",
            headers={
                "Authorization": "Bearer real-oauth-token",
                "x-local-guest-id": "guest_old_session",   # must be ignored
            },
        )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "oauth-user-github-999"
