"""
Tests unitaires pour les routes FastAPI.
Teste les endpoints /api/ask et /api/reindex.
"""
import json
from collections import deque
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from src.api.routes import register_routes
from src.api.auth import get_current_user
from src.api.limiter import limiter, rate_limit_handler


def create_client(user_id: str = "user_test") -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.dependency_overrides[get_current_user] = lambda: user_id
    register_routes(app, deque(maxlen=100))
    return TestClient(app)


def parse_sse(content: bytes) -> list:
    """Extrait les événements JSON d'une réponse SSE."""
    events = []
    for line in content.decode().splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ===== TESTS POUR /api/ask =====

@patch("src.api.routes.index_data")
@patch("src.api.routes.rechercher_passages")
@patch("src.api.routes.stream_reponse")
def test_ask_question_valide(mock_stream, mock_rechercher, mock_index):
    """On peut poser une question valide et recevoir une réponse streamée."""
    mock_index.return_value = True
    mock_rechercher.return_value = (["Passage 1", "Passage 2"], ["source1.md", "source2.md"], [0.9, 0.8])
    mock_stream.return_value = iter(["Réponse ", "de l'IA"])

    response = create_client().post("/api/ask",
                                    json={"question": "Qui est le héros?", "user_id": "user_test"})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = parse_sse(response.content)
    text_events = [e for e in events if e.get("type") == "text"]
    full_text = "".join(e["text"] for e in text_events)
    assert full_text == "Réponse de l'IA"

    meta = next((e for e in events if e.get("type") == "meta"), None)
    assert meta is not None
    assert meta["sources"] == ["source1.md", "source2.md"]

    mock_rechercher.assert_called_once_with("Qui est le héros?")


@patch("src.api.routes.index_data")
def test_ask_question_vide(mock_index):
    """Une question vide renvoie une erreur."""
    mock_index.return_value = True
    response = create_client().post("/api/ask", json={"question": ""})
    assert response.status_code == 400
    assert response.json()["error"] == "Question vide"


@patch("src.api.routes.index_data")
@patch("src.api.routes.rechercher_passages")
def test_ask_aucun_passage_trouve(mock_rechercher, mock_index):
    """Quand aucun passage n'est trouvé, on reçoit un message d'information."""
    mock_index.return_value = True
    mock_rechercher.return_value = ([], [], [])

    response = create_client().post("/api/ask",
                                    json={"question": "Question inconnue", "user_id": "user_test"})

    assert response.status_code == 200
    assert "archives ne contiennent aucune information" in response.text


@patch("src.api.routes.index_data")
@patch("src.api.routes.rechercher_passages")
@patch("src.api.routes.stream_reponse")
def test_ask_erreur_generation(mock_stream, mock_rechercher, mock_index):
    """Si la génération échoue, un événement erreur est envoyé dans le stream."""
    mock_index.return_value = True
    mock_rechercher.return_value = (["Passage"], ["source.md"], [0.8])
    mock_stream.side_effect = Exception("Erreur API")

    response = create_client().post("/api/ask",
                                    json={"question": "Question", "user_id": "user_test"})

    assert response.status_code == 200
    events = parse_sse(response.content)
    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert error_event["message"] == "Une erreur interne est survenue."


# ===== TESTS POUR LE QUERY REWRITING =====

@patch("src.api.routes.index_data")
@patch("src.api.routes.get_history")
@patch("src.api.routes.reformuler_question")
@patch("src.api.routes.rechercher_passages")
@patch("src.api.routes.stream_reponse")
def test_ask_utilise_question_reformulee(mock_stream, mock_rechercher, mock_reformuler,
                                         mock_history, mock_index):
    """La question reformulée est utilisée pour la recherche RAG."""
    mock_index.return_value = True
    mock_history.return_value = [{"question": "Qui est Lucas ?", "answer": "Un guerrier."}]
    mock_reformuler.return_value = "Quelle est la taille de Lucas le Tranchant ?"
    mock_rechercher.return_value = (["Lucas mesure 1m30."], ["lore.md"], [0.9])
    mock_stream.return_value = iter(["1m30"])

    create_client().post("/api/ask",
                         json={"question": "il fait quelle taille ?",
                               "session_id": "abc", "user_id": "user_test"})

    mock_reformuler.assert_called_once_with("il fait quelle taille ?", mock_history.return_value)
    mock_rechercher.assert_called_once_with("Quelle est la taille de Lucas le Tranchant ?")


@patch("src.api.routes.index_data")
@patch("src.api.routes.get_history")
@patch("src.api.routes.reformuler_question")
@patch("src.api.routes.rechercher_passages")
@patch("src.api.routes.stream_reponse")
def test_ask_sans_historique_pas_de_reformulation(mock_stream, mock_rechercher, mock_reformuler,
                                                   mock_history, mock_index):
    """Sans historique, reformuler_question retourne la question originale."""
    mock_index.return_value = True
    mock_history.return_value = []
    mock_reformuler.return_value = "Qui est le roi ?"
    mock_rechercher.return_value = (["Le roi est Alaric."], ["lore.md"], [0.9])
    mock_stream.return_value = iter(["Alaric"])

    create_client().post("/api/ask",
                         json={"question": "Qui est le roi ?", "user_id": "user_test"})

    mock_reformuler.assert_called_once_with("Qui est le roi ?", [])
    mock_rechercher.assert_called_once_with("Qui est le roi ?")


# ===== TESTS POUR /api/reindex =====

@patch("src.api.routes.index_data")
@patch("src.api.auth._MONITORING_KEY", "test_key")
def test_reindex_sans_force(mock_index):
    mock_index.return_value = True
    response = create_client().post("/api/reindex", json={}, headers={"X-Monitoring-Key": "test_key"})
    assert response.status_code == 200
    assert "terminée" in response.json()["message"]
    mock_index.assert_called_once_with(force_reindex=False)


@patch("src.api.routes.index_data")
@patch("src.api.auth._MONITORING_KEY", "test_key")
def test_reindex_avec_force(mock_index):
    mock_index.return_value = True
    response = create_client().post("/api/reindex", json={"force": True}, headers={"X-Monitoring-Key": "test_key"})
    assert response.status_code == 200
    mock_index.assert_called_once_with(force_reindex=True)


@patch("src.api.routes.index_data")
@patch("src.api.auth._MONITORING_KEY", "test_key")
def test_reindex_erreur(mock_index):
    mock_index.side_effect = Exception("Erreur d'indexation")
    response = create_client().post("/api/reindex", json={}, headers={"X-Monitoring-Key": "test_key"})
    assert response.status_code == 500
    assert "Erreur interne lors de la réindexation." in response.json()["error"]
