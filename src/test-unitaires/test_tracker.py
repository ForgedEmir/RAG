"""
Tests unitaires pour le module monitoring/tracker.
Teste get_history, save_exchange et track avec le schéma conversations/messages.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock, AsyncMock

_VALID_SESSION = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-session"))


# ===== TESTS POUR get_history =====

@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_get_history_sans_client(mock_get_client):
    """Sans client Supabase, retourne une liste vide sans erreur."""
    from src.monitoring.tracker import get_history
    mock_get_client.return_value = None
    assert await get_history("session-abc") == []


@pytest.mark.asyncio
async def test_get_history_session_vide():
    """Avec un session_id vide, retourne une liste vide sans appel Supabase."""
    from src.monitoring.tracker import get_history
    assert await get_history("") == []


@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_get_history_retourne_echanges(mock_get_client):
    """Retourne les paires {question, answer} dans l'ordre chronologique."""
    from src.monitoring.tracker import get_history

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Premier appel : conversations → retourne l'id
    conv_result = MagicMock()
    conv_result.data = [{"id": 42}]

    # Deuxième appel : messages → retourne les messages (desc, puis reversed dans le code)
    messages_result = MagicMock()
    messages_result.data = [
        {"role": "assistant", "content": "Deuxieme reponse"},
        {"role": "user",      "content": "Deuxieme question"},
        {"role": "assistant", "content": "Premiere reponse"},
        {"role": "user",      "content": "Premiere question"},
    ]

    # On chaîne les mocks selon l'ordre d'appel
    # .execute() doit être un AsyncMock
    table_mock = mock_client.table.return_value
    
    # Mock pour _get_conv_id (conversations)
    conv_exec_mock = AsyncMock(return_value=conv_result)
    table_mock.select.return_value.eq.return_value.limit.return_value.execute = conv_exec_mock
    
    # Mock pour les messages
    messages_exec_mock = AsyncMock(return_value=messages_result)
    table_mock.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = messages_exec_mock

    # WHY: On doit aussi gérer le cas où select() est appelé sans paramètres ou avec d'autres
    # mais ici le code appelle séquentiellement.

    resultat = await get_history(_VALID_SESSION)

    assert len(resultat) == 2
    assert resultat[0]["question"] == "Premiere question"
    assert resultat[0]["answer"] == "Premiere reponse"
    assert resultat[1]["question"] == "Deuxieme question"


@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_get_history_erreur_supabase(mock_get_client):
    """Si Supabase echoue, retourne une liste vide sans lever d'exception."""
    from src.monitoring.tracker import get_history

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.table.side_effect = Exception("Connexion refusee")

    assert await get_history("session-abc") == []


# ===== TESTS POUR save_exchange =====

@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_save_exchange_sans_client(mock_get_client):
    """Sans client Supabase, ne leve pas d'exception."""
    from src.monitoring.tracker import save_exchange
    mock_get_client.return_value = None
    await save_exchange("session-abc", "Question", "Reponse")


@pytest.mark.asyncio
async def test_save_exchange_session_vide():
    """Avec un session_id vide, n'insere rien."""
    from src.monitoring.tracker import save_exchange
    await save_exchange("", "Question", "Reponse")


@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_save_exchange_insere_correctement(mock_get_client):
    """Insere 2 messages (user + assistant) dans la table messages."""
    from src.monitoring.tracker import save_exchange

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Mock _get_or_create_conversation : conversations.select → pas de résultat → insert
    conv_select = MagicMock()
    conv_select.data = []  # conversation n'existe pas encore
    conv_insert = MagicMock()
    conv_insert.data = [{"id": 99}]

    # On doit gérer les deux appels successifs à table("conversations")
    conversations_table = MagicMock()
    conversations_table.select.return_value.eq.return_value.limit.return_value.execute = AsyncMock(return_value=conv_select)
    conversations_table.insert.return_value.execute = AsyncMock(return_value=conv_insert)

    messages_table = MagicMock()
    messages_table.insert.return_value.execute = AsyncMock()

    def table_router(name):
        if name == "conversations":
            return conversations_table
        if name == "messages":
            return messages_table
        return MagicMock()

    mock_client.table.side_effect = table_router

    await save_exchange(_VALID_SESSION, "Qui est Lucas ?", "Lucas est un guerrier.", "user-1")

    # Vérifie que 2 messages ont été insérés
    insert_call = messages_table.insert.call_args[0][0]
    assert len(insert_call) == 2
    assert insert_call[0]["role"] == "user"
    assert insert_call[0]["content"] == "Qui est Lucas ?"
    assert insert_call[1]["role"] == "assistant"
    assert insert_call[1]["content"] == "Lucas est un guerrier."
    assert insert_call[0]["conversation_id"] == 99


# ===== TESTS POUR track =====

@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_track_sans_client(mock_get_client):
    """Sans client Supabase, ne leve pas d'exception."""
    from src.monitoring.tracker import track
    mock_get_client.return_value = None
    await track("question", detail="Test", latency_ms=500)


@pytest.mark.asyncio
@patch('src.monitoring.tracker._get_client', new_callable=AsyncMock)
async def test_track_insere_evenement(mock_get_client):
    """Insere un evenement avec les bons champs."""
    from src.monitoring.tracker import track

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    exec_mock = AsyncMock()
    mock_client.table.return_value.insert.return_value.execute = exec_mock

    await track("question", detail="Qui est Lucas ?", latency_ms=300)

    insert_data = mock_client.table.return_value.insert.call_args[0][0]
    assert insert_data["type"] == "question"
    assert insert_data["detail"] == "Qui est Lucas ?"
    assert insert_data["latency_ms"] == 300
