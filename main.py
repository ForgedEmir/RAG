"""
C'est le point d'entrée de notre projet.
Son rôle est simple : préparer l'application, démarrer le serveur web (Flask) 
et s'assurer que notre base de connaissances est à jour au lancement.
"""
import sys
import os
import logging

# On configure les logs pour voir ce qu'il se passe dans la console.
# Le format 'date - niveau - message' est classique et facile à lire au besoin.
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Petite astuce pour que Python trouve facilement nos dossiers "src" : 
# on ajoute la racine du projet au PATH système.
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from flask import Flask
from flask_cors import CORS
from src.api.routes import register_routes
from src.ingestion.run import index_data

# On initialise notre serveur web
app = Flask(__name__)

# Le CORS est indispensable si jamais on veut séparer le frontend du backend plus tard.
# Ça autorise les navigateurs à discuter avec notre API sans bloquer pour raisons de sécurité.
CORS(app)

# On charge toutes les URL (routes) définies dans notre dossier api
register_routes(app)

if __name__ == "__main__":
    # Avant même d'ouvrir les portes du serveur, on vérifie si 
    # de nouveaux fichiers de lore ont été ajoutés dans le dossier 'data'.
    index_data(force_reindex=False)

    # C'est parti, on lance le serveur ! 
    # Le debug=True est super pratique en développement car ça recharge le code tout seul.
    app.run(host="0.0.0.0", port=5000, debug=True)
