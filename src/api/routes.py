from flask import request, jsonify, send_from_directory
import os
from src.search.recherche import rechercher_passages
from src.generation.generateur import generer_reponse

# Définir le chemin du dossier frontend
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "frontend"))

def register_routes(app):
    """
    Enregistre toutes les routes de l'application
    """
    
    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(frontend_dir, path)

    @app.route("/api/ask", methods=["POST"])
    def ask():
        try:
            data = request.get_json()
            question = data.get("question", "")
            
            if not question:
                return jsonify({"error": "Question vide"}), 400
            
            # Rechercher les passages pertinents avec le RAG
            passages, question_retournee = rechercher_passages(question)
            
            if not passages:
                return jsonify({"reponse": "Les archives mystiques ne contiennent aucune information sur ce sujet..."})
            
            # Générer la réponse avec DeepSeek
            reponse = generer_reponse(question, passages)
            return jsonify({"reponse": reponse})
        
        except Exception as e:
            print(f"Erreur: {e}")
            return jsonify({"error": str(e)}), 500
