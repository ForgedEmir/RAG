"""
Point d'entrée principal de l'application Oracle des Archives
Lance le serveur Flask avec toutes les routes configurées
"""
import sys
import os

# Chzmins
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from flask import Flask
from flask_cors import CORS
from src.api.routes import register_routes

# Créer l'application Flask
app = Flask(__name__)
CORS(app)  

# Enregistrer les routes
register_routes(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
