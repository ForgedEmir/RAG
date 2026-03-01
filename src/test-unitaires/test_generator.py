"""
Tests unitaires simplifiés pour le module generator

Ce fichier teste la fonction qui génère des réponses avec l'IA (DeepSeek).
On simule l'API pour ne pas faire de vrais appels (qui coûteraient de l'argent).
"""

# Import pour simuler l'API
from unittest.mock import Mock, patch
# Import de la fonction à tester
from src.generation.generator import generer_reponse


# ===== TESTS POUR generer_reponse =====

@patch('src.generation.generator._client')
def test_generation_simple(mock_client):
    """On peut générer une réponse simple avec l'IA."""
    # On simule la réponse de l'API
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "  Réponse de l'IA  "
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    # On appelle la fonction
    question = "Qui est le héros?"
    passages = ["Le héros s'appelle Arthur."]
    sources = ["personnages.md"]
    
    resultat = generer_reponse(question, passages, sources)
    
    # On vérifie le résultat (les espaces sont enlevés)
    assert resultat == "Réponse de l'IA"


@patch('src.generation.generator._client')
def test_plusieurs_passages(mock_client):
    """On peut générer une réponse avec plusieurs passages."""
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "Réponse complète"
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    question = "Décris le royaume"
    passages = [
        "Le royaume est grand.",
        "Il y a une forêt.",
        "La capitale est belle."
    ]
    sources = ["lieux.md"]
    
    resultat = generer_reponse(question, passages, sources)
    
    # On vérifie que tous les passages ont été envoyés
    appel = mock_client.chat.completions.create.call_args
    messages = appel.kwargs['messages']
    contexte = messages[0]['content']
    
    assert "Le royaume est grand." in contexte
    assert "Il y a une forêt." in contexte


@patch('src.generation.generator._client')
def test_sans_sources(mock_client):
    """Si aucune source n'est fournie, ça marche quand même."""
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "Réponse"
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    question = "Question"
    passages = ["Passage"]
    
    resultat = generer_reponse(question, passages, sources=None)
    
    assert resultat == "Réponse"
    # On vérifie que "sources inconnues" apparaît dans le prompt
    appel = mock_client.chat.completions.create.call_args
    messages = appel.kwargs['messages']
    assert "sources inconnues" in messages[0]['content']


@patch('src.generation.generator._client', None)
def test_sans_api_key():
    """Sans clé API, une erreur est levée."""
    question = "Question"
    passages = ["Passage"]
    
    try:
        generer_reponse(question, passages)
        # Si on arrive ici, le test échoue car l'erreur n'a pas été levée
        assert False, "Une erreur aurait dû être levée"
    except ValueError as e:
        # On vérifie que le message d'erreur est correct
        assert "OPENAI_API_KEY" in str(e)


@patch('src.generation.generator._client')
def test_parametres_api(mock_client):
    """On vérifie que l'API est appelée avec les bons paramètres."""
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "Réponse"
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    generer_reponse("Question", ["Passage"], ["test.md"])
    
    # On récupère les arguments de l'appel
    appel = mock_client.chat.completions.create.call_args
    
    # On vérifie les paramètres importants
    assert appel.kwargs['model'] == "deepseek-chat"
    assert appel.kwargs['temperature'] == 0.2  # Température basse = factuel
    assert len(appel.kwargs['messages']) == 2  # System + User
    assert appel.kwargs['messages'][0]['role'] == "system"
    assert appel.kwargs['messages'][1]['role'] == "user"


@patch('src.generation.generator._client')
def test_contexte_formate(mock_client):
    """Les passages sont séparés par des doubles sauts de ligne."""
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "Réponse"
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    passages = ["Passage 1", "Passage 2", "Passage 3"]
    generer_reponse("Question", passages, ["test.md"])
    
    appel = mock_client.chat.completions.create.call_args
    system_message = appel.kwargs['messages'][0]['content']
    
    # Les passages doivent être séparés par \n\n
    assert "Passage 1\n\nPassage 2\n\nPassage 3" in system_message


@patch('src.generation.generator._client')
def test_instructions_rag(mock_client):
    """Le prompt contient les instructions RAG."""
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "Réponse"
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    generer_reponse("Question", ["Passage"], ["test.md"])
    
    appel = mock_client.chat.completions.create.call_args
    system_message = appel.kwargs['messages'][0]['content']
    
    # Vérifier que les instructions importantes sont là
    assert "Aethelgard Online" in system_message
    assert "uniquement en te basant" in system_message
    assert "N'invente" in system_message


@patch('src.generation.generator._client')
def test_espaces_enleves(mock_client):
    """Les espaces au début et fin de réponse sont enlevés."""
    reponse_simulee = Mock()
    reponse_simulee.choices = [Mock()]
    reponse_simulee.choices[0].message.content = "\n\n  Réponse  \n\n"
    mock_client.chat.completions.create.return_value = reponse_simulee
    
    resultat = generer_reponse("Question", ["Passage"])
    
    # Les espaces et sauts de ligne doivent être enlevés
    assert resultat == "Réponse"
    assert not resultat.startswith(" ")
    assert not resultat.endswith(" ")
