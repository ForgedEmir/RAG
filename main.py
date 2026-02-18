"""
Point d'entrée principal de l'application Oracle des Archives
Lance le serveur Flask avec toutes les routes configurées
"""
import sys
import os

# Chemins
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from flask import Flask
from flask_cors import CORS
from src.api.routes import register_routes
from src.ingestion.run import indexer_donnees

# Créer l'application Flask
app = Flask(__name__)
CORS(app)  

# Enregistrer les routes
register_routes(app)

if __name__ == "__main__":
    # Éviter l'affichage double en mode debug (reloader Flask)
    # WERKZEUG_RUN_MAIN est défini uniquement après le redémarrage du reloader
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    
    if not is_reloader_process:
        print("=" * 50)
        print("🔮 L'Oracle des Archives s'éveille...")
        print("=" * 50)
        
        # Afficher le chemin de la DB pour vérification
        db_path = os.path.join(project_root, "src", "ingestion", "chroma_db")
        print(f"📂 DB ChromaDB: {os.path.abspath(db_path)}")
    
    # Indexer les données si nécessaire (avec détection automatique des changements)
    indexer_donnees(force_reindex=False, auto_detect_changes=True)
    
    if not is_reloader_process:
        print("=" * 50)
        print("📍 Serveur accessible sur :")
        print("   - Local : http://127.0.0.1:5000")
        print("   - Réseau : http://192.168.x.x:5000")
        print("=" * 50)
    
    app.run(host="0.0.0.0", port=5000, debug=True)
