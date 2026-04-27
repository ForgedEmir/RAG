"""
Tests unitaires pour les routes FastAPI.
Teste les endpoints /api/ask et /api/reindex.
"""
import json
from collections import deque
from unittest.mock import patch, AsyncMock
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
@patch("src.api.routes.rechercher_passages", new_callable=AsyncMock)
@patch("src.api.routes.stream_reponse")
@patch("src.api.routes.track", new_callable=AsyncMock)
@patch("src.api.routes.register_trace_context", new_callable=AsyncMock)
@patch("src.api.routes.cache_check", new_callable=AsyncMock)
@patch("src.api.routes.valider_entree", new_callable=AsyncMock)
def test_ask_question_valide(mock_valider, mock_cache, mock_reg, mock_track, mock_stream, mock_rechercher, mock_index):
    """On peut poser une question valide et recevoir une réponse streamée."""
    mock_index.return_value = True
    mock_valider.return_value = {"valid": True}
    mock_cache.return_value = None
    mock_rechercher.return_value = (["Passage 1", "Passage 2"], ["source1.md", "source2.md"], [0.9, 0.8], set())
    
    async def mock_stream_gen(*args, **kwargs):
        yield "Réponse "
        yield "de l'IA"
    mock_stream.side_effect = mock_stream_gen

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

    done_evt = next((e for e in events if e.get("type") == "done"), None)
    assert done_evt is not None
    assert isinstance(done_evt.get("trace_id"), str)
    assert len(done_evt["trace_id"]) >= 8
    assert done_evt.get("question_for_feedback") == "Qui est le héros?"

    mock_rechercher.assert_called_once_with("Qui est le héros?")


@patch("src.api.routes.index_data")
def test_ask_question_vide(mock_index):
    """Une question vide renvoie une erreur."""
    mock_index.return_value = True
    response = create_client().post("/api/ask", json={"question": ""})
    assert response.status_code == 400
    assert response.json()["error"] == "Question vide"


@patch("src.api.routes.index_data")
@patch("src.api.routes.rechercher_passages", new_callable=AsyncMock)
@patch("src.api.routes.valider_entree", new_callable=AsyncMock)
@patch("src.api.routes.cache_check", new_callable=AsyncMock)
@patch("src.api.routes.register_trace_context", new_callable=AsyncMock)
def test_ask_aucun_passage_trouve(mock_reg, mock_cache, mock_valider, mock_rechercher, mock_index):
    """Quand aucun passage n'est trouvé, on reçoit un message d'information."""
    mock_index.return_value = True
    mock_valider.return_value = {"valid": True}
    mock_cache.return_value = None
    mock_rechercher.return_value = ([], [], [], set())

    response = create_client().post("/api/ask",
                                    json={"question": "Question inconnue", "user_id": "user_test"})

    assert response.status_code == 200
    assert "archives ne contiennent aucune information" in response.text


@patch("src.api.routes.index_data")
@patch("src.api.routes.rechercher_passages", new_callable=AsyncMock)
@patch("src.api.routes.stream_reponse")
@patch("src.api.routes.valider_entree", new_callable=AsyncMock)
@patch("src.api.routes.cache_check", new_callable=AsyncMock)
@patch("src.api.routes.track", new_callable=AsyncMock)
def test_ask_erreur_generation(mock_track, mock_cache, mock_valider, mock_stream, mock_rechercher, mock_index):
    """Si la génération échoue, un événement erreur est envoyé dans le stream."""
    mock_index.return_value = True
    mock_valider.return_value = {"valid": True}
    mock_cache.return_value = None
    mock_rechercher.return_value = (["Passage"], ["source.md"], [0.8], set())
    
    async def mock_stream_error(*args, **kwargs):
        if False: yield "" # make it a generator
        raise Exception("Erreur API")
    mock_stream.side_effect = mock_stream_error

    response = create_client().post("/api/ask",
                                    json={"question": "Question", "user_id": "user_test"})

    assert response.status_code == 200
    events = parse_sse(response.content)
    error_event = next((e for e in events if e.get("type") == "error"), None)
    assert error_event is not None
    assert "Erreur API" in error_event["message"]


# ===== TESTS POUR LE QUERY REWRITING =====

@patch("src.api.routes.index_data")
@patch("src.api.routes.get_history", new_callable=AsyncMock)
@patch("src.api.routes.reformuler_question", new_callable=AsyncMock)
@patch("src.api.routes.rechercher_passages", new_callable=AsyncMock)
@patch("src.api.routes.stream_reponse")
@patch("src.api.routes.valider_entree", new_callable=AsyncMock)
@patch("src.api.routes.cache_check", new_callable=AsyncMock)
@patch("src.api.routes.register_trace_context", new_callable=AsyncMock)
@patch("src.api.routes.track", new_callable=AsyncMock)
@patch("src.api.routes.save_exchange", new_callable=AsyncMock)
@patch("src.api.routes.cache_store", new_callable=AsyncMock)
def test_ask_utilise_question_reformulee(mock_store, mock_save, mock_track, mock_reg, mock_cache, mock_valider, mock_stream, mock_rechercher, mock_reformuler,
                                         mock_history, mock_index):
    """La question reformulée est utilisée pour la recherche RAG."""
    mock_index.return_value = True
    mock_valider.return_value = {"valid": True}
    mock_cache.return_value = None
    mock_history.return_value = [{"question": "Qui est Lucas ?", "answer": "Un guerrier."}]
    mock_reformuler.return_value = "Quelle est la taille de Lucas le Tranchant ?"
    mock_rechercher.return_value = (["Lucas mesure 1m30."], ["lore.md"], [0.9], set())
    
    async def mock_stream_gen(*args, **kwargs):
        yield "1m30"
    mock_stream.side_effect = mock_stream_gen

    create_client().post("/api/ask",
                         json={"question": "il fait quelle taille ?",
                               "session_id": "abc", "user_id": "user_test"})

    mock_reformuler.assert_called_once_with("il fait quelle taille ?", mock_history.return_value)
    mock_rechercher.assert_called_once_with("Quelle est la taille de Lucas le Tranchant ?")


@patch("src.api.routes.index_data")
@patch("src.api.routes.get_history", new_callable=AsyncMock)
@patch("src.api.routes.reformuler_question", new_callable=AsyncMock)
@patch("src.api.routes.rechercher_passages", new_callable=AsyncMock)
@patch("src.api.routes.stream_reponse")
@patch("src.api.routes.valider_entree", new_callable=AsyncMock)
@patch("src.api.routes.cache_check", new_callable=AsyncMock)
def test_ask_sans_historique_pas_de_reformulation(mock_cache, mock_valider, mock_stream, mock_rechercher, mock_reformuler,
                                                   mock_history, mock_index):
    """Sans historique, reformuler_question retourne la question originale."""
    mock_index.return_value = True
    mock_valider.return_value = {"valid": True}
    mock_cache.return_value = None
    mock_history.return_value = []
    mock_reformuler.return_value = "Qui est le roi ?"
    mock_rechercher.return_value = (["Le roi est Alaric."], ["lore.md"], [0.9], set())
    
    async def mock_stream_gen(*args, **kwargs):
        yield "Alaric"
    mock_stream.side_effect = mock_stream_gen

    create_client().post("/api/ask",
                         json={"question": "Qui est le roi ?", "user_id": "user_test"})

    mock_reformuler.assert_called_once_with("Qui est le roi ?", [])
    mock_rechercher.assert_called_once_with("Qui est le roi ?")


# ===== TESTS POUR /api/reindex =====

@patch("src.api.routes.index_data")
@patch("src.api.auth._MONITORING_KEY", "test_key")
@patch("src.api.routes.track", new_callable=AsyncMock)
def test_reindex_sans_force(mock_track, mock_index):
    mock_index.return_value = True
    response = create_client().post("/api/reindex", json={}, headers={"X-Monitoring-Key": "test_key"})
    assert response.status_code == 200
    assert "terminée" in response.json()["message"]
    mock_index.assert_called_once_with(force_reindex=False)


@patch("src.api.routes.index_data")
@patch("src.api.auth._MONITORING_KEY", "test_key")
@patch("src.api.routes.track", new_callable=AsyncMock)
def test_reindex_avec_force(mock_track, mock_index):
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
    # Depuis le durcissement, le message d'erreur est générique
    assert "Erreur interne" in response.json()["error"]


@patch("src.api.auth._MONITORING_KEY", "test_key")
@patch("src.monitoring.tracker.get_recent_feedback_events", new_callable=AsyncMock)
def test_monitoring_feedbacks_endpoint(mock_feedbacks):
    mock_feedbacks.return_value = [{"trace_id": "trace-1", "value": 1, "rating": 5}]
    response = create_client().get("/api/monitoring/feedbacks?limit=10", headers={"X-Monitoring-Key": "test_key"})
    assert response.status_code == 200
    assert response.json()["feedbacks"][0]["trace_id"] == "trace-1"
