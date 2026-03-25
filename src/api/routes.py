"""
Routes de l'API Flask.
Reçoit les questions, streame les réponses, gère l'admin et le monitoring.
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


def _get_rate_limit_key() -> str:
    """Clé de rate limit : session_id si dispo, sinon IP.
    Permet à plusieurs users sur la même IP d'avoir des limites indépendantes.
    """
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "").strip()
    return session_id if session_id else get_remote_address()


def register_routes(app: Flask) -> None:

    limiter = Limiter(
        _get_rate_limit_key,
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
        return send_from_directory(frontend_dir, "monitoring.html")

    @app.route("/<path:path>")
    def serve_static(path: str):
        return send_from_directory(frontend_dir, path)

    # ── API principale ───────────────────────────────────────────────────────

    @app.route("/api/ask", methods=["POST"])
    @limiter.limit("1 per 5 seconds")
    @limiter.limit("10 per minute")
    @limiter.limit("100 per day")
    def ask():
        """Reçoit une question et streame la réponse token par token (SSE)."""
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

    # ── Indexation ───────────────────────────────────────────────────────────

    @app.route("/api/reindex", methods=["POST"])
    @limiter.limit("5 per hour")
    def reindex():
        """Force une réindexation des fichiers."""
        try:
            force = (request.get_json(silent=True) or {}).get("force", False)
            resultat = index_data(force_reindex=force)
            if resultat:
                from src.search.search import invalidate_bm25_cache
                invalidate_bm25_cache()
            msg = "Indexation terminée avec succès." if resultat else "La base est déjà à jour."
            track("reindex", detail=f"force={force} | {'changements' if resultat else 'aucun changement'}")
            return jsonify({"message": msg})
        except Exception as e:
            logger.error(f"Erreur reindex : {e}")
            return jsonify({"error": str(e)}), 500

    # ── Conversations ────────────────────────────────────────────────────────

    @app.route("/api/conversations")
    def conversations():
        """Retourne les échanges d'une session."""
        session_id = request.args.get("session_id", "")
        if not session_id:
            return jsonify({"error": "session_id requis"}), 400
        return jsonify({"exchanges": get_conversation(session_id)})

    @app.route("/api/conversations", methods=["DELETE"])
    def delete_conv():
        """Supprime une conversation."""
        session_id = request.args.get("session_id", "")
        if not session_id:
            return jsonify({"error": "session_id requis"}), 400
        delete_conversation(session_id)
        return jsonify({"ok": True})

    # ── TTS / STT ────────────────────────────────────────────────────────────

    @app.route("/api/tts", methods=["POST"])
    @limiter.limit("30 per minute")
    def tts():
        """Synthèse vocale via Edge TTS."""
        try:
            from src.tts.tts import generer_audio
            text = (request.get_json() or {}).get("text", "")
            if not text:
                return jsonify({"error": "Texte vide"}), 400
            audio = generer_audio(text)
            track("tts", detail=f"{len(text)} chars")
            return Response(audio, mimetype="audio/mpeg")
        except Exception as e:
            logger.error(f"Erreur TTS : {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/stt", methods=["POST"])
    @limiter.limit("20 per minute")
    def stt():
        """Transcription audio via Groq Whisper."""
        try:
            audio = request.files.get("audio")
            if not audio:
                return jsonify({"error": "Aucun fichier audio"}), 400
            from openai import OpenAI
            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url="https://api.groq.com/openai/v1",
            )
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=(audio.filename or "audio.webm", audio.read()),
                language="fr",
            )
            track("voice", detail=f"whisper | {audio.filename or 'audio.webm'}")
            return jsonify({"text": transcription.text})
        except Exception as e:
            logger.error(f"Erreur STT : {e}")
            return jsonify({"error": str(e)}), 500

    # ── Monitoring & Admin ───────────────────────────────────────────────────

    @app.route("/api/monitoring/stats")
    def monitoring_stats():
        if not _check_monitoring_key():
            return jsonify({"error": "Accès refusé"}), 403
        return jsonify(get_stats())

    @app.route("/api/admin/sources")
    def admin_sources():
        """Liste les fichiers lore indexés."""
        if not _check_monitoring_key():
            return jsonify({"error": "Accès refusé"}), 403
        from src.ingestion.run import list_current_files
        fichiers = list_current_files()
        return jsonify({"files": sorted(fichiers.keys()), "total": len(fichiers)})

    @app.route("/api/admin/upload", methods=["POST"])
    @limiter.limit("20 per hour")
    def admin_upload():
        """Upload un fichier lore."""
        if not _check_monitoring_key():
            return jsonify({"error": "Accès refusé"}), 403
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"error": "Aucun fichier"}), 400

        ALLOWED = {".txt", ".md", ".csv", ".json", ".xml", ".xlsx"}
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED:
            return jsonify({"error": f"Extension non supportée. Formats : {', '.join(ALLOWED)}"}), 400

        raw = f.read()

        # Max 500 Ko
        MAX_SIZE = 500 * 1024
        if len(raw) > MAX_SIZE:
            return jsonify({"error": f"Fichier trop volumineux ({len(raw)//1024} Ko). Max : 500 Ko."}), 400

        # Vérification anti-injection sur un échantillon du fichier
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            return jsonify({"error": "Impossible de lire le fichier (encodage invalide)."}), 400

        lines = text.splitlines()
        mid = len(lines) // 2
        sample_lines = lines[:20] + lines[max(0, mid - 5) : mid + 5] + lines[-20:]
        sample = "\n".join(sample_lines) or text[:2000]

        from src.security.validator import valider_entree
        check = valider_entree(sample)
        if not check["valid"]:
            logger.warning(f"Upload bloqué [{check['type']}] — '{f.filename}'")
            track("upload_blocked", detail=f"{f.filename} | raison:{check['type']}")
            return jsonify({"error": "Contenu suspect détecté. Upload refusé."}), 400

        data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
        os.makedirs(data_dir, exist_ok=True)
        dest = os.path.join(data_dir, os.path.basename(f.filename))
        with open(dest, "wb") as out:
            out.write(raw)

        logger.info(f"Fichier uploadé : {f.filename} ({len(raw)//1024} Ko)")
        track("upload", detail=f"{f.filename} | {len(raw)//1024} Ko")
        return jsonify({"message": f"'{f.filename}' uploadé ({len(raw)//1024} Ko). Lance une réindexation pour l'activer.", "filename": f.filename})

    @app.route("/api/admin/delete", methods=["DELETE"])
    def admin_delete():
        """Supprime un fichier lore."""
        if not _check_monitoring_key():
            return jsonify({"error": "Accès refusé"}), 403
        filename = (request.get_json(silent=True) or {}).get("filename", "").strip()
        if not filename or "/" in filename or "\\" in filename or ".." in filename:
            return jsonify({"error": "Nom de fichier invalide"}), 400
        data_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "sample"))
        path = os.path.join(data_dir, filename)
        if not os.path.exists(path):
            return jsonify({"error": "Fichier introuvable"}), 404
        os.remove(path)
        track("reindex", detail=f"suppression : {filename}")
        logger.info(f"Fichier supprimé : {filename}")
        return jsonify({"message": f"'{filename}' supprimé. Réindexe pour mettre à jour Qdrant."})

    @app.errorhandler(429)
    def trop_de_requetes(e):
        track("rate_limit", detail=request.remote_addr)
        return jsonify({
            "error": "Trop de requêtes. Merci de patienter.",
            "blocked": True, "block_type": "rate_limit",
        }), 429
