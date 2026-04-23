import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from langchain_core.messages import AIMessage


# ===== TESTS POUR generer_reponse =====

def _mock_llm_with_fallbacks(mock_llm, ai_response: str):
    """Configure mock_llm.with_fallbacks().ainvoke() pour retourner ai_response."""
    chain_mock = MagicMock()
    chain_mock.ainvoke = AsyncMock(return_value=AIMessage(content=ai_response))
    mock_llm.with_fallbacks.return_value = chain_mock
    return chain_mock


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_generation_simple(mock_llm):
    """On peut generer une reponse simple avec l'IA."""
    from src.generation.generator import generer_reponse

    _mock_llm_with_fallbacks(mock_llm, "  Reponse de l'IA  ")

    question = "Qui est le heros?"
    passages = ["Le heros s'appelle Arthur."]
    sources = ["personnages.md"]

    resultat = await generer_reponse(question, passages, sources)

    assert resultat == "Reponse de l'IA"


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_plusieurs_passages(mock_llm):
    """On peut generer une reponse avec plusieurs passages."""
    from src.generation.generator import generer_reponse

    chain_mock = _mock_llm_with_fallbacks(mock_llm, "Reponse complete")

    question = "Decris le royaume"
    passages = [
        "Le royaume est grand.",
        "Il y a une foret.",
        "La capitale est belle."
    ]
    sources = ["lieux.md"]

    await generer_reponse(question, passages, sources)

    # On verifie que les passages ont ete envoyes dans le message system
    appel = chain_mock.ainvoke.call_args
    messages = appel[0][0]
    system_content = messages[0].content

    assert "Le royaume est grand." in system_content
    assert "Il y a une foret." in system_content


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_sans_sources(mock_llm):
    """Si aucune source n'est fournie, ca marche quand meme."""
    from src.generation.generator import generer_reponse

    chain_mock = _mock_llm_with_fallbacks(mock_llm, "Reponse")

    resultat = await generer_reponse("Question", ["Passage"], sources=None)

    assert resultat == "Reponse"
    appel = chain_mock.ainvoke.call_args
    messages = appel[0][0]
    assert "sources inconnues" in messages[0].content


@pytest.mark.asyncio
@patch('src.generation.generator._llm', None)
async def test_sans_api_key():
    """Sans cle API, une erreur est levee."""
    from src.generation.generator import generer_reponse

    try:
        await generer_reponse("Question", ["Passage"])
        assert False, "Une erreur aurait du etre levee"
    except ValueError as e:
        assert "OPENAI_API_KEY" in str(e)


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_parametres_llm(mock_llm):
    """On verifie que le LLM est appele avec les bons messages."""
    from src.generation.generator import generer_reponse

    chain_mock = _mock_llm_with_fallbacks(mock_llm, "Reponse")

    await generer_reponse("Question", ["Passage"], ["test.md"])

    appel = chain_mock.ainvoke.call_args
    messages = appel[0][0]

    assert len(messages) == 2
    assert messages[0].__class__.__name__ == "SystemMessage"
    assert messages[1].__class__.__name__ == "HumanMessage"
    assert messages[1].content == "Question"


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_contexte_formate(mock_llm):
    """Les passages sont separes par des doubles sauts de ligne."""
    from src.generation.generator import generer_reponse

    chain_mock = _mock_llm_with_fallbacks(mock_llm, "Reponse")

    passages = ["Passage 1", "Passage 2", "Passage 3"]
    await generer_reponse("Question", passages, ["test.md"])

    appel = chain_mock.ainvoke.call_args
    system_message = appel[0][0][0].content

    assert "Passage 1\n\nPassage 2\n\nPassage 3" in system_message


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_instructions_rag(mock_llm):
    """Le prompt contient les instructions RAG."""
    from src.generation.generator import generer_reponse

    chain_mock = _mock_llm_with_fallbacks(mock_llm, "Reponse")

    await generer_reponse("Question", ["Passage"], ["test.md"])

    appel = chain_mock.ainvoke.call_args
    system_message = appel[0][0][0].content

    assert "Aethelgard Online" in system_message
    assert "uniquement à partir du contexte fourni" in system_message or "uniquement en te basant" in system_message
    assert "n'invente rien" in system_message.lower()


# ===== TESTS POUR reformuler_question =====

@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_reformuler_sans_historique(mock_llm):
    """Sans historique, la question originale est retournee sans appel LLM."""
    from src.generation.generator import reformuler_question

    resultat = await reformuler_question("Qui est Lucas ?", [])

    assert resultat == "Qui est Lucas ?"
    mock_llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
@patch('src.generation.generator._llm_fallback')
@patch('src.generation.generator._llm_reformulation')
async def test_reformuler_avec_historique(mock_llm_ref, mock_llm_fb, mock_llm):
    """Avec historique, le LLM est appele et la question reformulee est retournee."""
    from src.generation.generator import reformuler_question

    # On s'assure que tous les LLM possibles retournent la même chose
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Quelle est la taille de Lucas ?"))
    mock_llm_fb.ainvoke = AsyncMock(return_value=AIMessage(content="Quelle est la taille de Lucas ?"))
    mock_llm_ref.ainvoke = AsyncMock(return_value=AIMessage(content="Quelle est la taille de Lucas ?"))

    # Historique avec 2 échanges pour dépasser le seuil de skip
    history = [
        {"question": "Qui est Lucas ?", "answer": "Lucas est un guerrier d'1m30."},
        {"question": "Où vit-il ?", "answer": "Dans la capitale."},
    ]
    resultat = await reformuler_question("il fait quelle taille ?", history)

    assert resultat == "Quelle est la taille de Lucas ?"
    # On vérifie qu'au moins un des LLM a été appelé
    assert mock_llm.ainvoke.called or mock_llm_fb.ainvoke.called or mock_llm_ref.ainvoke.called


@pytest.mark.asyncio
@patch('src.generation.generator._llm', None)
@patch('src.generation.generator._llm_fallback', None)
@patch('src.generation.generator._llm_reformulation', None)
async def test_reformuler_llm_indisponible():
    """Sans LLM disponible, la question originale est retournee."""
    from src.generation.generator import reformuler_question

    history = [{"question": "Qui est Lucas ?", "answer": "Un guerrier."}]
    resultat = await reformuler_question("il fait quelle taille ?", history)

    assert resultat == "il fait quelle taille ?"


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
@patch('src.generation.generator._llm_fallback', None)
@patch('src.generation.generator._llm_reformulation', None)
async def test_reformuler_erreur_llm(mock_llm):
    """Si le LLM echoue, la question originale est retournee (fail-silent)."""
    from src.generation.generator import reformuler_question

    mock_llm.ainvoke = AsyncMock(side_effect=Exception("Erreur reseau"))

    history = [{"question": "Qui est Lucas ?", "answer": "Un guerrier."}]
    resultat = await reformuler_question("il fait quelle taille ?", history)

    assert resultat == "il fait quelle taille ?"


@pytest.mark.asyncio
@patch('src.generation.generator._llm')
async def test_stream_reponse(mock_llm):
    """On peut streamer une reponse token par token."""
    from src.generation.generator import stream_reponse

    # Mock astream
    async def mock_astream(*args, **kwargs):
        yield MagicMock(content="Token 1 ")
        yield MagicMock(content="Token 2")

    mock_llm.astream = mock_astream

    tokens = []
    async for t in stream_reponse("Question ?", ["Passage"]):
        tokens.append(t)

    assert tokens == ["Token 1 ", "Token 2"]
