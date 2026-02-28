"""
Ce fichier configure les routes (URL) de l'application.
- "/" sert la page web du frontend
- "/api/ask" reçoit les questions de l'utilisateur et renvoie la réponse de l'IA
- "/api/reindex" permet de relancer l'indexation des données manuellement
"""
import logging
from flask import Flask, request, jsonify, send_from_directory
import os
from src.search.search import rechercher_passages
from src.generation.generator import generer_reponse
from src.ingestion.run import index_data

# Créer un logger pour ce module
logger = logging.getLogger(__name__)

# Chemin vers le dossier qui contient le site web (HTML, CSS, JS)
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "frontend"))


def register_routes(app: Flask) -> None:
    """Enregistre toutes les routes de l'application Flask."""

    # Route principale : affiche la page d'accueil
    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    # Route pour servir les fichiers CSS, JS, images, etc.
    @app.route("/<path:path>")
    def serve_static(path: str):
        return send_from_directory(frontend_dir, path)

    # Route API : reçoit une question et renvoie la réponse de l'IA
    @app.route("/api/ask", methods=["POST"])
    def ask():
        try:
            data = request.get_json()
            question = data.get("question", "")

            if not question:
                return jsonify({"error": "Question vide"}), 400

            # Étape 0 : vérifier s'il y a de nouveaux fichiers à indexer
            index_data(force_reindex=False)

            # Étape 1 : chercher les passages pertinents dans la base de données
            passages, sources = rechercher_passages(question)

            if not passages:
                return jsonify({
                    "reponse": "Les archives ne contiennent aucune information sur ce sujet.",
                    "sources": []
                })

            # Étape 2 : envoyer les passages + la question à l'IA pour générer une réponse
            reponse = generer_reponse(question, passages, sources)

            return jsonify({
                "reponse": reponse,
                "sources": sources
            })

        except Exception as e:
            logger.error(f"Erreur dans /api/ask : {e}")
            return jsonify({"error": str(e)}), 500

    # Route API : relance l'indexation des données (nouveaux fichiers, etc.)
    @app.route("/api/reindex", methods=["POST"])
    def reindex():
        """
        Permet de relancer l'indexation sans redémarrer le serveur.
        Marcus veut pouvoir déposer un fichier et que le système le détecte.
        """
        try:
            force = request.get_json(silent=True) or {}
            force_reindex = force.get("force", False)

            resultat = index_data(force_reindex=force_reindex)

            if resultat:
                return jsonify({"message": "Indexation terminée avec succès."})
            else:
                return jsonify({"message": "La base de données est déjà à jour."})

        except Exception as e:
            logger.error(f"Erreur dans /api/reindex : {e}")
            return jsonify({"error": str(e)}), 500
