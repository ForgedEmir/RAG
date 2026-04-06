"""
Tests unitaires pour le module generator (version LangChain)

Ce fichier teste la fonction qui genere des reponses avec l'IA.
On simule le LLM LangChain pour ne pas faire de vrais appels (qui couteraient de l'argent).
"""
from unittest.mock import Mock, patch, MagicMock
from langchain_core.messages import AIMessage


# ===== TESTS POUR generer_reponse =====

@patch('src.generation.generator._llm')
def test_generation_simple(mock_llm):
    """On peut generer une reponse simple avec l'IA."""
    from src.generation.generator import generer_reponse

    # On simule la reponse LangChain
    mock_llm.invoke.return_value = AIMessage(content="  Reponse de l'IA  ")

    question = "Qui est le heros?"
    passages = ["Le heros s'appelle Arthur."]
    sources = ["personnages.md"]

    resultat = generer_reponse(question, passages, sources)

    # On verifie le resultat (les espaces sont enleves)
    assert resultat == "Reponse de l'IA"


@patch('src.generation.generator._llm')
def test_plusieurs_passages(mock_llm):
    """On peut generer une reponse avec plusieurs passages."""
    from src.generation.generator import generer_reponse

    mock_llm.invoke.return_value = AIMessage(content="Reponse complete")

    question = "Decris le royaume"
    passages = [
        "Le royaume est grand.",
        "Il y a une foret.",
        "La capitale est belle."
    ]
    sources = ["lieux.md"]

    resultat = generer_reponse(question, passages, sources)

    # On verifie que les passages ont ete envoyes dans le message system
    appel = mock_llm.invoke.call_args
    messages = appel[0][0]  # Premier argument positionnel = liste de messages
    system_content = messages[0].content

    assert "Le royaume est grand." in system_content
    assert "Il y a une foret." in system_content


@patch('src.generation.generator._llm')
def test_sans_sources(mock_llm):
    """Si aucune source n'est fournie, ca marche quand meme."""
    from src.generation.generator import generer_reponse

    mock_llm.invoke.return_value = AIMessage(content="Reponse")

    resultat = generer_reponse("Question", ["Passage"], sources=None)

    assert resultat == "Reponse"
    # On verifie que "sources inconnues" apparait dans le prompt
    appel = mock_llm.invoke.call_args
    messages = appel[0][0]
    assert "sources inconnues" in messages[0].content


@patch('src.generation.generator._llm', None)
def test_sans_api_key():
    """Sans cle API, une erreur est levee."""
    from src.generation.generator import generer_reponse

    try:
        generer_reponse("Question", ["Passage"])
        assert False, "Une erreur aurait du etre levee"
    except ValueError as e:
        assert "OPENAI_API_KEY" in str(e)


@patch('src.generation.generator._llm')
def test_parametres_llm(mock_llm):
    """On verifie que le LLM est appele avec les bons messages."""
    from src.generation.generator import generer_reponse

    mock_llm.invoke.return_value = AIMessage(content="Reponse")

    generer_reponse("Question", ["Passage"], ["test.md"])

    # On recupere les arguments de l'appel
    appel = mock_llm.invoke.call_args
    messages = appel[0][0]

    # On verifie : 2 messages (System + Human)
    assert len(messages) == 2
    assert messages[0].__class__.__name__ == "SystemMessage"
    assert messages[1].__class__.__name__ == "HumanMessage"
    assert messages[1].content == "Question"


@patch('src.generation.generator._llm')
def test_contexte_formate(mock_llm):
    """Les passages sont separes par des doubles sauts de ligne."""
    from src.generation.generator import generer_reponse

    mock_llm.invoke.return_value = AIMessage(content="Reponse")

    passages = ["Passage 1", "Passage 2", "Passage 3"]
    generer_reponse("Question", passages, ["test.md"])

    appel = mock_llm.invoke.call_args
    system_message = appel[0][0][0].content

    # Les passages doivent etre separes par \n\n
    assert "Passage 1\n\nPassage 2\n\nPassage 3" in system_message


@patch('src.generation.generator._llm')
def test_instructions_rag(mock_llm):
    """Le prompt contient les instructions RAG."""
    from src.generation.generator import generer_reponse

    mock_llm.invoke.return_value = AIMessage(content="Reponse")

    generer_reponse("Question", ["Passage"], ["test.md"])

    appel = mock_llm.invoke.call_args
    system_message = appel[0][0][0].content

    # Verifier que les instructions importantes sont la
    assert "Aethelgard Online" in system_message
    assert "uniquement en te basant" in system_message
    assert "N'invente" in system_message


# ===== TESTS POUR reformuler_question =====

@patch('src.generation.generator._llm')
def test_reformuler_sans_historique(mock_llm):
    """Sans historique, la question originale est retournee sans appel LLM."""
    from src.generation.generator import reformuler_question

    resultat = reformuler_question("Qui est Lucas ?", [])

    assert resultat == "Qui est Lucas ?"
    mock_llm.invoke.assert_not_called()


@patch('src.generation.generator._llm')
def test_reformuler_avec_historique(mock_llm):
    """Avec historique, le LLM est appele et la question reformulee est retournee."""
    from src.generation.generator import reformuler_question

    mock_llm.invoke.return_value = AIMessage(content="Quelle est la taille de Lucas le Tranchant ?")

    # Historique avec 2 échanges pour dépasser le seuil de skip (≤1 échange + ≤5 mots)
    history = [
        {"question": "Qui est Lucas ?", "answer": "Lucas est un guerrier d'1m30."},
        {"question": "Où vit-il ?", "answer": "Dans la capitale."},
    ]
    resultat = reformuler_question("il fait quelle taille ?", history)

    assert resultat == "Quelle est la taille de Lucas le Tranchant ?"
    mock_llm.invoke.assert_called_once()


@patch('src.generation.generator._llm', None)
def test_reformuler_llm_indisponible():
    """Sans LLM disponible, la question originale est retournee."""
    from src.generation.generator import reformuler_question

    history = [{"question": "Qui est Lucas ?", "answer": "Un guerrier."}]
    resultat = reformuler_question("il fait quelle taille ?", history)

    assert resultat == "il fait quelle taille ?"


@patch('src.generation.generator._llm')
def test_reformuler_erreur_llm(mock_llm):
    """Si le LLM echoue, la question originale est retournee (fail-silent)."""
    from src.generation.generator import reformuler_question

    mock_llm.invoke.side_effect = Exception("Erreur reseau")

    history = [{"question": "Qui est Lucas ?", "answer": "Un guerrier."}]
    resultat = reformuler_question("il fait quelle taille ?", history)

    assert resultat == "il fait quelle taille ?"
