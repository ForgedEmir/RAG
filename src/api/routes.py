"""
Fichier de configuration des routes (les URL de notre site).
C'est ici qu'on fait le pont entre ce que l'utilisateur tape sur l'interface
et notre logique Python derrière.
"""
import logging
import os
import secrets
from collections import deque
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, session
from src.search.search import rechercher_passages
from src.generation.generator import generer_reponse
from src.ingestion.run import index_data, DATA_FOLDER, SUPPORTED_EXTENSIONS
from src.security.validator import valider_entree

logger = logging.getLogger(__name__)

# Chemin vers nos fichiers HTML/JS
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "frontend"))

# Historique en mémoire des 50 dernières questions posées à l'Oracle
_query_history: deque = deque(maxlen=50)

# Mot de passe admin (configurable via .env)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")


def register_routes(app: Flask) -> None:

    # ── Décorateur de protection des routes admin ────────────────────────────
    def admin_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("admin_authenticated"):
                return jsonify({"error": "Non autorisé"}), 401
            return f(*args, **kwargs)
        return decorated

    # ── ROUTES PUBLIQUES ─────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/admin")
    def admin():
        return send_from_directory(frontend_dir, "admin.html")

    @app.route("/<path:path>")
    def serve_static(path: str):
        return send_from_directory(frontend_dir, path)

    @app.route("/api/ask", methods=["POST"])
    def ask():
        """Cœur du système : reçoit la question, cherche dans les archives, répond."""
        try:
            data = request.get_json()
            question = data.get("question", "")

            if not question:
                return jsonify({"error": "Question vide"}), 400

            # ── Validation de sécurité ────────────────────────────────────────
            validation = valider_entree(question, type_entree="question")
            if not validation["valid"]:
                if validation["type"] == "prompt_injection":
                    msg = (
                        "⚠️ L'Oracle a détecté une tentative de manipulation des arcanes sacrées. "
                        "Cette invocation ne peut être traitée. "
                        "Posez une question sincère sur le lore pour consulter les archives."
                    )
                else:
                    msg = (
                        "🔮 L'Oracle ne peut répondre qu'aux questions sur le lore du jeu. "
                        "Cette question semble hors du domaine des archives mystiques. "
                        "Interrogez-moi sur les personnages, lieux, artefacts ou événements du monde."
                    )
                logger.info(f"Question bloquée [{validation['type']}] : {question[:80]}")
                _query_history.appendleft({
                    "question": question,
                    "reponse": msg,
                    "passages": [],
                    "sources": [],
                    "timestamp": datetime.now().isoformat(),
                    "blocked": True,
                    "block_type": validation["type"],
                })
                return jsonify({
                    "reponse": msg,
                    "sources": [],
                    "passages": [],
                    "blocked": True,
                    "block_type": validation["type"],
                })

            index_data(force_reindex=False)
            passages, sources = rechercher_passages(question)

            if not passages:
                return jsonify({
                    "reponse": "Les archives ne contiennent aucune information sur ce sujet.",
                    "sources": [],
                    "passages": [],
                    "blocked": False,
                })

            reponse = generer_reponse(question, passages, sources)

            # Stockage dans l'historique pour l'interface admin
            _query_history.appendleft({
                "question": question,
                "reponse": reponse,
                "passages": passages,
                "sources": sources,
                "timestamp": datetime.now().isoformat(),
            })

            return jsonify({
                "reponse": reponse,
                "sources": sources,
                "passages": passages,
                "blocked": False,
            })

        except Exception as e:
            logger.error(f"Erreur dans /api/ask : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/reindex", methods=["POST"])
    def reindex():
        """Force la mise à jour des données sans redémarrer le serveur."""
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

    # ── ROUTES ADMIN ─────────────────────────────────────────────────────────

    @app.route("/api/admin/login", methods=["POST"])
    def admin_login():
        data = request.get_json() or {}
        if data.get("password") == ADMIN_PASSWORD:
            session["admin_authenticated"] = True
            session["admin_token"] = secrets.token_hex(16)
            return jsonify({"success": True})
        return jsonify({"error": "Mot de passe incorrect"}), 401

    @app.route("/api/admin/logout", methods=["POST"])
    def admin_logout():
        session.clear()
        return jsonify({"success": True})

    @app.route("/api/admin/status", methods=["GET"])
    def admin_status():
        return jsonify({"authenticated": bool(session.get("admin_authenticated"))})

    @app.route("/api/admin/stats", methods=["GET"])
    @admin_required
    def admin_stats():
        try:
            from src.ingestion.vector_store import get_collection_stats
            stats = get_collection_stats()
            file_count = 0
            if os.path.exists(DATA_FOLDER):
                file_count = sum(
                    1 for f in os.listdir(DATA_FOLDER)
                    if f.lower().endswith(SUPPORTED_EXTENSIONS)
                )
            stats["file_count"] = file_count
            stats["query_count"] = len(_query_history)
            return jsonify(stats)
        except Exception as e:
            logger.error(f"Erreur stats admin : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/files", methods=["GET"])
    @admin_required
    def admin_files():
        try:
            from src.ingestion.vector_store import count_chunks_by_file
            chunks_by_file = count_chunks_by_file()
            files = []
            if os.path.exists(DATA_FOLDER):
                for nom in os.listdir(DATA_FOLDER):
                    if nom.lower().endswith(SUPPORTED_EXTENSIONS):
                        chemin = os.path.join(DATA_FOLDER, nom)
                        stat = os.stat(chemin)
                        files.append({
                            "name": nom,
                            "size": stat.st_size,
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                            "chunks": chunks_by_file.get(nom, 0),
                        })
            files.sort(key=lambda x: x["name"])
            return jsonify({"files": files})
        except Exception as e:
            logger.error(f"Erreur liste fichiers admin : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/files/<path:filename>", methods=["DELETE"])
    @admin_required
    def admin_delete_file(filename):
        try:
            safe_folder = os.path.realpath(DATA_FOLDER)
            target = os.path.realpath(os.path.join(DATA_FOLDER, filename))
            if not target.startswith(safe_folder + os.sep):
                return jsonify({"error": "Accès refusé"}), 403

            if not os.path.exists(target):
                return jsonify({"error": "Fichier introuvable"}), 404

            from src.ingestion.vector_store import get_store, remove_files
            from src.ingestion.run import load_memory, save_memory
            store = get_store()
            remove_files(store, {filename})

            memoire = load_memory()
            memoire.pop(filename, None)
            save_memory(memoire)

            os.remove(target)
            return jsonify({"success": True, "message": f"'{filename}' supprimé des archives."})
        except Exception as e:
            logger.error(f"Erreur suppression fichier admin : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/files/<path:filename>/content", methods=["GET"])
    @admin_required
    def admin_file_content(filename):
        try:
            safe_folder = os.path.realpath(DATA_FOLDER)
            target = os.path.realpath(os.path.join(DATA_FOLDER, filename))
            if not target.startswith(safe_folder + os.sep):
                return jsonify({"error": "Accès refusé"}), 403

            if not os.path.exists(target):
                return jsonify({"error": "Fichier introuvable"}), 404

            # Les fichiers binaires (xlsx) ne peuvent pas être lus comme texte
            binary_exts = (".xlsx",)
            if filename.lower().endswith(binary_exts):
                return jsonify({
                    "filename": filename,
                    "content": "[Fichier binaire — aperçu non disponible. Utilisez le testeur de recherche pour voir les passages indexés.]",
                })

            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return jsonify({"filename": filename, "content": content})
        except Exception as e:
            logger.error(f"Erreur lecture contenu fichier : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/upload", methods=["POST"])
    @admin_required
    def admin_upload():
        try:
            if "files" not in request.files:
                return jsonify({"error": "Aucun fichier reçu"}), 400

            files = request.files.getlist("files")
            os.makedirs(DATA_FOLDER, exist_ok=True)
            uploaded = []
            errors = []

            for file in files:
                if not file.filename:
                    continue
                nom = os.path.basename(file.filename)
                if not nom.lower().endswith(SUPPORTED_EXTENSIONS):
                    errors.append(f"{nom} : format non supporté")
                    continue

                # Lire le contenu pour le vérifier avant de sauvegarder
                contenu_bytes = file.read()
                file.seek(0)

                # Vérification du contenu : injection ET pertinence thématique
                if not nom.lower().endswith(".xlsx"):
                    try:
                        contenu_texte = contenu_bytes.decode("utf-8", errors="replace")
                        check = valider_entree(contenu_texte, type_entree="fichier")
                        if not check["valid"]:
                            if check["type"] == "prompt_injection":
                                errors.append(f"{nom} : contenu suspect détecté (tentative d'injection)")
                            else:
                                errors.append(f"{nom} : contenu hors-sujet — ce fichier ne semble pas contenir du lore de jeu")
                            logger.warning(f"Upload bloqué [{nom}] [{check['type']}] : {check['reason']}")
                            continue
                    except Exception:
                        pass  # En cas d'erreur de lecture, on laisse passer

                chemin = os.path.join(DATA_FOLDER, nom)
                file.save(chemin)
                uploaded.append(nom)

            if uploaded:
                index_data(force_reindex=False)

            return jsonify({
                "uploaded": uploaded,
                "errors": errors,
                "message": f"{len(uploaded)} fichier(s) importé(s) dans les archives.",
            })
        except Exception as e:
            logger.error(f"Erreur upload admin : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/reindex", methods=["POST"])
    @admin_required
    def admin_reindex():
        try:
            data = request.get_json(silent=True) or {}
            force = data.get("force", True)
            index_data(force_reindex=force)
            msg = "Réindexation complète terminée." if force else "Mise à jour incrémentale terminée."
            return jsonify({"success": True, "message": msg})
        except Exception as e:
            logger.error(f"Erreur reindex admin : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/search-test", methods=["POST"])
    @admin_required
    def admin_search_test():
        """Teste le moteur de recherche et retourne les passages bruts avec leurs sources."""
        try:
            data = request.get_json() or {}
            question = data.get("question", "")
            if not question:
                return jsonify({"error": "Question vide"}), 400
            passages, sources = rechercher_passages(question)
            return jsonify({
                "passages": passages,
                "sources": sources,
                "count": len(passages),
            })
        except Exception as e:
            logger.error(f"Erreur search-test admin : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/admin/queries", methods=["GET"])
    @admin_required
    def admin_queries():
        """Retourne l'historique des questions posées à l'Oracle."""
        return jsonify({"queries": list(_query_history)})
