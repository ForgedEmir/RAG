"""
Fichier de configuration des routes (les URL de notre site).
C'est ici qu'on fait le pont entre ce que l'utilisateur tape sur l'interface
et notre logique Python derrière.
"""
import logging
from flask import Flask, request, jsonify, send_from_directory
import os
from src.search.search import rechercher_passages
from src.generation.generator import generer_reponse
from src.ingestion.run import index_data

logger = logging.getLogger(__name__)

# On garde sous le coude le chemin vers nos fichiers HTML/JS
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "frontend"))

def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        # Quand on tape l'URL de base, on renvoie la page d'accueil
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:path>")
    def serve_static(path: str):
        # Sert à distribuer le CSS, le JS et les images
        return send_from_directory(frontend_dir, path)

    @app.route("/api/ask", methods=["POST"])
    def ask():
        """C'est le cœur du système : on reçoit la question, on cherche, et on répond."""
        try:
            data = request.get_json()
            question = data.get("question", "")

            if not question:
                return jsonify({"error": "Question vide"}), 400

            # Première étape de sécurité : vérifier qu'on est bien à jour sur les fichiers
            index_data(force_reindex=False)

            # On part à la pêche aux infos dans notre base de données ChromaDB
            passages, sources = rechercher_passages(question)

            # Si on ne trouve rien du tout de pertinent, on évite d'inventer des choses
            if not passages:
                return jsonify({
                    "reponse": "Les archives ne contiennent aucune information sur ce sujet.",
                    "sources": []
                })

            # On donne la question et le contexte à l'IA pour qu'elle rédige une belle phrase
            reponse = generer_reponse(question, passages, sources)

            return jsonify({
                "reponse": reponse,
                "sources": sources
            })

        except Exception as e:
            logger.error(f"Erreur dans /api/ask : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/reindex", methods=["POST"])
    def reindex():
        """
        Un petit endpoint pratique pour forcer la mise à jour des données 
        sans avoir à redémarrer tout le programme manuellement.
        """
        try:
            force = request.get_json(silent=True) or {}
            force_reindex = force.get("force", False)

            resultat = index_data(force_reindex=force_reindex)

            if resultat:
                return jsonify({"message": "Indexation terminée avec succès."})
            else:
                return jsonify({"message": "La base de données est déjà à jour, rien à faire."})

        except Exception as e:
            logger.error(f"Erreur au moment de re-indexer : {e}")
            return jsonify({"error": str(e)}), 500
