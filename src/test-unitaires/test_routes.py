"""
Tests unitaires pour le module routes (API Flask)
Teste les endpoints /api/ask et /api/reindex.
"""

from unittest.mock import Mock, patch
from flask import Flask
import json

from src.api.routes import register_routes


# Note importante pour les débutants :
# On simule les fonctions de recherche et génération pour tester seulement l'API.
# Ça permet de vérifier que les routes Flask répondent correctement.


def creer_app_test():
    """Fonction qui crée une application Flask pour les tests."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    register_routes(app)
    return app


# ===== TESTS POUR /api/ask =====

@patch('src.api.routes.index_data')
@patch('src.api.routes.rechercher_passages')
@patch('src.api.routes.generer_reponse')
def test_ask_question_valide(mock_generer, mock_rechercher, mock_index):
    """On peut poser une question valide et recevoir une réponse."""
    # On prépare les fausses réponses
    mock_index.return_value = True
    mock_rechercher.return_value = (
        ["Passage 1", "Passage 2"],
        ["source1.md", "source2.md"]
    )
    mock_generer.return_value = "Réponse de l'IA"
    
    # On crée l'appli et on envoie une requête
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/ask', 
                          json={'question': 'Qui est le héros?'},
                          content_type='application/json')
    
    # On vérifie la réponse
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['reponse'] == "Réponse de l'IA"
    assert data['sources'] == ["source1.md", "source2.md"]
    # On vérifie que les fonctions ont été appelées
    mock_rechercher.assert_called_once_with('Qui est le héros?')
    mock_generer.assert_called_once()
    mock_index.assert_called_once_with(force_reindex=False)


@patch('src.api.routes.index_data')
def test_ask_question_vide(mock_index):
    """Une question vide renvoie une erreur."""
    mock_index.return_value = True
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/ask',
                          json={'question': ''},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert data['error'] == "Question vide"


@patch('src.api.routes.index_data')
def test_ask_sans_question(mock_index):
    """Sans le champ 'question', on a une erreur."""
    mock_index.return_value = True
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/ask',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data


@patch('src.api.routes.index_data')
@patch('src.api.routes.rechercher_passages')
def test_ask_aucun_passage_trouve(mock_rechercher, mock_index):
    """Quand aucun passage n'est trouvé, on reçoit un message d'information."""
    mock_index.return_value = True
    mock_rechercher.return_value = ([], [])
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/ask',
                          json={'question': 'Question inconnue'},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "archives ne contiennent aucune information" in data['reponse']
    assert data['sources'] == []


@patch('src.api.routes.index_data')
@patch('src.api.routes.rechercher_passages')
@patch('src.api.routes.generer_reponse')
def test_ask_erreur_generation(mock_generer, mock_rechercher, mock_index):
    """Si la génération échoue, on reçoit une erreur 500."""
    mock_index.return_value = True
    mock_rechercher.return_value = (["Passage"], ["source.md"])
    mock_generer.side_effect = Exception("Erreur API")
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/ask',
                          json={'question': 'Question'},
                          content_type='application/json')
    
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert "Erreur API" in data['error']


# ===== TESTS POUR /api/reindex =====

@patch('src.api.routes.index_data')
def test_reindex_sans_force(mock_index):
    """On peut réindexer sans forcer (indexe seulement si nécessaire)."""
    mock_index.return_value = True
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/reindex',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "succès" in data['message']
    mock_index.assert_called_once_with(force_reindex=False)


@patch('src.api.routes.index_data')
def test_reindex_avec_force(mock_index):
    """On peut forcer une réindexation complète."""
    mock_index.return_value = True
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/reindex',
                          json={'force': True},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "succès" in data['message']
    mock_index.assert_called_once_with(force_reindex=True)


@patch('src.api.routes.index_data')
def test_reindex_rien_a_faire(mock_index):
    """Quand tout est déjà à jour, on reçoit un message approprié."""
    mock_index.return_value = False
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/reindex',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "déjà à jour" in data['message']


@patch('src.api.routes.index_data')
def test_reindex_erreur(mock_index):
    """Si l'indexation échoue, on reçoit une erreur 500."""
    mock_index.side_effect = Exception("Erreur d'indexation")
    
    app = creer_app_test()
    client = app.test_client()
    response = client.post('/api/reindex',
                          json={},
                          content_type='application/json')
    
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert "Erreur d'indexation" in data['error']


# ===== TESTS POUR LES ROUTES STATIQUES =====

@patch('src.api.routes.send_from_directory')
def test_route_index(mock_send):
    """La route / renvoie le fichier index.html."""
    mock_send.return_value = "HTML content"
    
    app = creer_app_test()
    client = app.test_client()
    response = client.get('/')
    
    assert response.status_code == 200
    mock_send.assert_called_once()
    # Vérifie que le fichier index.html est demandé
    call_args = mock_send.call_args
    assert "index.html" in str(call_args)


@patch('src.api.routes.send_from_directory')
def test_route_statique(mock_send):
    """Les routes statiques renvoient les fichiers correspondants."""
    mock_send.return_value = "Static file content"
    
    app = creer_app_test()
    client = app.test_client()
    response = client.get('/style.css')
    
    assert response.status_code == 200
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert "style.css" in str(call_args)
