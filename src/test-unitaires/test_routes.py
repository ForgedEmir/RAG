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


# ===== TESTS POUR /api/ingestion/status =====

@patch('src.api.routes.load_ingestion_report')
def test_ingestion_status_avec_rapport(mock_load_report):
    """Test du statut d'ingestion quand un rapport existe."""
    # Simuler un rapport d'ingestion
    mock_load_report.return_value = {
        "fichiers_traites": 5,
        "fichiers_rejetes": 2,
        "fichiers_ignores": 1,
        "chunks_crees": 123,
        "duree_secondes": 1.45,
        "timestamp": "2026-03-04T10:30:00",
        "details_rejetes": [
            {"fichier": "bad.txt", "erreurs": ["Encodage invalide"]}
        ],
        "details_ignores": [
            {"fichier": "test.py", "extension": ".py"}
        ]
    }
    
    app = creer_app_test()
    client = app.test_client()
    response = client.get('/api/ingestion/status')
    
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'success'
    assert data['report']['fichiers_traites'] == 5
    assert data['report']['fichiers_rejetes'] == 2
    assert data['report']['fichiers_ignores'] == 1
    assert data['report']['chunks_crees'] == 123
    assert data['report']['duree_secondes'] == 1.45
    assert len(data['report']['details_rejetes']) == 1
    assert len(data['report']['details_ignores']) == 1


@patch('src.api.routes.load_ingestion_report')
def test_ingestion_status_sans_rapport(mock_load_report):
    """Test du statut d'ingestion quand aucun rapport n'existe."""
    mock_load_report.return_value = None
    
    app = creer_app_test()
    client = app.test_client()
    response = client.get('/api/ingestion/status')
    
    assert response.status_code == 404
    data = json.loads(response.data)
    assert data['status'] == 'no_report'
    assert 'Aucun rapport' in data['message']


@patch('src.api.routes.load_ingestion_report')
def test_ingestion_status_erreur(mock_load_report):
    """Test du statut d'ingestion en cas d'erreur."""
    mock_load_report.side_effect = Exception("Erreur de lecture")
    
    app = creer_app_test()
    client = app.test_client()
    response = client.get('/api/ingestion/status')
    
    assert response.status_code == 500
    data = json.loads(response.data)
    assert 'error' in data
    assert "Erreur de lecture" in data['error']
