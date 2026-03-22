"""
Routes de l'API Flask.
Reçoit les questions des utilisateurs et retourne les réponses de l'Oracle.
"""
import json
import logging
import os
import time

from flask import Flask, Response, request, jsonify, send_from_directory, stream_with_context
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from src.search.search import rechercher_passages
from src.generation.generator import stream_reponse, reformuler_question
from src.ingestion.run import index_data
from src.security.validator import valider_entree
from src.monitoring.tracker import track, get_stats, get_history, save_exchange, get_conversation, delete_conversation

logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dir = os.path.abspath(os.path.join(current_dir, "..", "frontend"))

_MONITORING_KEY = os.getenv("MONITORING_KEY", "")


def _check_monitoring_key() -> bool:
    return request.args.get("key", "") == _MONITORING_KEY and _MONITORING_KEY != ""


def register_routes(app: Flask) -> None:

    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],
        storage_uri="memory://",
    )

    # ── Pages web ────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/monitoring")
    def monitoring():
        if not _check_monitoring_key():
            return jsonify({"error": "Accès refusé"}), 403
        return send_from_directory(frontend_dir, "monitoring.html")

    @app.route("/<path:path>")
    def serve_static(path: str):
        return send_from_directory(frontend_dir, path)

    # ── API ───────────────────────────────────────────────────────────────────

    @app.route("/api/ask", methods=["POST"])
    @limiter.limit("1 per 5 seconds")
    @limiter.limit("10 per minute")
    @limiter.limit("100 per day")
    def ask():
        """Reçoit une question et streame la réponse de l'Oracle token par token."""
        start = time.time()
        try:
            data = request.get_json() or {}
            question = data.get("question", "")
            session_id = data.get("session_id", "")

            if not question:
                return jsonify({"error": "Question vide"}), 400

            # Vérification de sécurité
            validation = valider_entree(question)
            if not validation["valid"]:
                block_type = validation["type"]
                is_lakera = "Lakera" in validation.get("reason", "")
                event_type = "injection_lakera" if (is_lakera or block_type == "jailbreak") else "injection_regex"
                track(event_type, detail=question[:200])

                msg = (
                    "⚠️ L'Oracle a détecté une tentative de manipulation des arcanes sacrées. "
                    "Posez une question sincère sur le lore pour consulter les archives."
                    if block_type in ("prompt_injection", "jailbreak") else
                    "🔮 L'Oracle ne peut répondre qu'aux questions sur le lore du jeu. "
                    "Interrogez-moi sur les personnages, lieux, artefacts ou événements du monde."
                )
                logger.info(f"Question bloquée [{block_type}] : {question[:80]}")
                return jsonify({
                    "reponse": msg, "sources": [], "passages": [],
                    "blocked": True, "block_type": block_type,
                })

            index_data(force_reindex=False)
            history = get_history(session_id)
            query = reformuler_question(question, history)
            passages, sources = rechercher_passages(query)

            if not passages:
                return jsonify({
                    "reponse": "Les archives ne contiennent aucune information sur ce sujet.",
                    "sources": [], "passages": [], "blocked": False,
                })

            def generate():
                accumulated = []
                model_used = []
                try:
                    yield f"data: {json.dumps({'type': 'meta', 'sources': sources, 'passages': passages})}\n\n"

                    for chunk in stream_reponse(question, passages, sources, history, model_used=model_used):
                        accumulated.append(chunk)
                        yield f"data: {json.dumps({'type': 'text', 'text': chunk})}\n\n"

                    model_name = model_used[0] if model_used else "inconnu"
                    yield f"data: {json.dumps({'type': 'done', 'model': model_name})}\n\n"

                    if session_id:
                        save_exchange(session_id, question, "".join(accumulated))

                    latency = int((time.time() - start) * 1000)
                    track("question", detail=f"{question[:150]} | model:{model_name}", latency_ms=latency)
                    logger.info(f"Réponse streamée via {model_name}.")

                except Exception as e:
                    track("error", detail=str(e)[:200])
                    logger.error(f"Erreur streaming : {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

            return Response(
                stream_with_context(generate()),
                mimetype="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )

        except Exception as e:
            track("error", detail=str(e)[:200])
            logger.error(f"Erreur dans /api/ask : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/reindex", methods=["POST"])
    @limiter.limit("5 per hour")
    def reindex():
        """Force une réindexation des fichiers sans redémarrer le serveur."""
        try:
            force = (request.get_json(silent=True) or {}).get("force", False)
            resultat = index_data(force_reindex=force)
            msg = "Indexation terminée avec succès." if resultat else "La base est déjà à jour."
            return jsonify({"message": msg})
        except Exception as e:
            logger.error(f"Erreur reindex : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/conversations")
    def conversations():
        """Retourne les échanges d'une session pour l'historique."""
        session_id = request.args.get("session_id", "")
        if not session_id:
            return jsonify({"error": "session_id requis"}), 400
        return jsonify({"exchanges": get_conversation(session_id)})

    @app.route("/api/conversations", methods=["DELETE"])
    def delete_conv():
        """Supprime une conversation de Supabase."""
        session_id = request.args.get("session_id", "")
        if not session_id:
            return jsonify({"error": "session_id requis"}), 400
        delete_conversation(session_id)
        return jsonify({"ok": True})

    @app.route("/api/tts", methods=["POST"])
    @limiter.limit("30 per minute")
    def tts():
        """Synthétise un texte en MP3 via Edge TTS (Microsoft Neural voices)."""
        try:
            from src.tts.tts import generer_audio
            text = (request.get_json() or {}).get("text", "")
            if not text:
                return jsonify({"error": "Texte vide"}), 400
            audio = generer_audio(text)
            return Response(audio, mimetype="audio/mpeg")
        except Exception as e:
            logger.error(f"Erreur TTS : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/monitoring/stats")
    def monitoring_stats():
        if not _check_monitoring_key():
            return jsonify({"error": "Accès refusé"}), 403
        return jsonify(get_stats())

    @app.errorhandler(429)
    def trop_de_requetes(e):
        track("rate_limit", detail=request.remote_addr)
        return jsonify({
            "error": "Trop de requêtes. Merci de patienter avant de consulter l'Oracle à nouveau.",
            "blocked": True, "block_type": "rate_limit",
        }), 429
