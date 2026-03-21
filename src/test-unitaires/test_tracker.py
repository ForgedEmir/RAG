"""
Tests unitaires pour le module monitoring/tracker.
Teste get_history, save_exchange et track.
"""
from unittest.mock import patch, MagicMock


# ===== TESTS POUR get_history =====

@patch('src.monitoring.tracker._get_client', return_value=None)
def test_get_history_sans_client(mock_client):
    """Sans client Supabase, retourne une liste vide sans erreur."""
    from src.monitoring.tracker import get_history

    resultat = get_history("session-abc")

    assert resultat == []


def test_get_history_session_vide():
    """Avec un session_id vide, retourne une liste vide sans appel Supabase."""
    from src.monitoring.tracker import get_history

    resultat = get_history("")

    assert resultat == []


@patch('src.monitoring.tracker._get_client')
def test_get_history_retourne_echanges(mock_get_client):
    """Retourne les echanges dans l'ordre chronologique (inverses depuis Supabase)."""
    from src.monitoring.tracker import get_history

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    echanges_supabase = [
        {"question": "Deuxieme question", "answer": "Deuxieme reponse"},
        {"question": "Premiere question", "answer": "Premiere reponse"},
    ]
    mock_client.table.return_value.select.return_value \
        .eq.return_value.order.return_value \
        .limit.return_value.execute.return_value.data = echanges_supabase

    resultat = get_history("session-abc")

    assert len(resultat) == 2
    assert resultat[0]["question"] == "Premiere question"
    assert resultat[1]["question"] == "Deuxieme question"


@patch('src.monitoring.tracker._get_client')
def test_get_history_erreur_supabase(mock_get_client):
    """Si Supabase echoue, retourne une liste vide sans lever d'exception."""
    from src.monitoring.tracker import get_history

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.side_effect = Exception("Connexion refusee")

    resultat = get_history("session-abc")

    assert resultat == []


# ===== TESTS POUR save_exchange =====

@patch('src.monitoring.tracker._get_client', return_value=None)
def test_save_exchange_sans_client(mock_client):
    """Sans client Supabase, ne leve pas d'exception."""
    from src.monitoring.tracker import save_exchange

    save_exchange("session-abc", "Question", "Reponse")  # ne doit pas crasher


def test_save_exchange_session_vide():
    """Avec un session_id vide, n'insere rien."""
    from src.monitoring.tracker import save_exchange

    save_exchange("", "Question", "Reponse")  # ne doit pas crasher


@patch('src.monitoring.tracker._get_client')
def test_save_exchange_insere_correctement(mock_get_client):
    """Insere l'echange avec les bons champs dans Supabase."""
    from src.monitoring.tracker import save_exchange

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    save_exchange("session-abc", "Qui est Lucas ?", "Lucas est un guerrier.")

    mock_client.table.assert_called_once_with("conversations")
    insert_data = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_data["session_id"] == "session-abc"
    assert insert_data["question"] == "Qui est Lucas ?"
    assert insert_data["answer"] == "Lucas est un guerrier."


# ===== TESTS POUR track =====

@patch('src.monitoring.tracker._get_client', return_value=None)
def test_track_sans_client(mock_client):
    """Sans client Supabase, ne leve pas d'exception."""
    from src.monitoring.tracker import track

    track("question", detail="Test", latency_ms=500)  # ne doit pas crasher


@patch('src.monitoring.tracker._get_client')
def test_track_insere_evenement(mock_get_client):
    """Insere un evenement avec les bons champs."""
    from src.monitoring.tracker import track

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    track("question", detail="Qui est Lucas ?", latency_ms=300)

    insert_data = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_data["type"] == "question"
    assert insert_data["detail"] == "Qui est Lucas ?"
    assert insert_data["latency_ms"] == 300
