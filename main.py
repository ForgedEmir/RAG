"""
Point d'entrée principal de l'application Oracle des Archives.
Ce fichier lance le serveur web Flask et indexe les données au démarrage.
"""
import sys
import os
import logging

# Configuration du logging pour tout le projet
# Format : [2024-01-15 14:30:00] INFO - Message
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# On ajoute le dossier du projet au PATH pour que Python trouve nos modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from flask import Flask
from flask_cors import CORS
from src.api.routes import register_routes
from src.ingestion.run import index_data

# Créer l'application Flask
app = Flask(__name__)
CORS(app)  # Permet au frontend d'appeler l'API sans erreur de sécurité navigateur

# On branche toutes les routes (pages web + API) à notre application
register_routes(app)

# Sur Vercel, on indexe les données au chargement du module (mode éphémère)
if os.environ.get("VERCEL") == "1":
    index_data(force_reindex=True)

if __name__ == "__main__":
    # Au démarrage local, on vérifie si de nouveaux fichiers doivent être ajoutés
    index_data(force_reindex=False)

    # Lancer le serveur sur le port 5000 (accessible depuis le navigateur)
    app.run(host="0.0.0.0", port=5000, debug=True)

