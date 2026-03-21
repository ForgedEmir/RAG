"""
Point d'entrée de l'application Oracle LoreKeeper.
"""
import sys
import os
import logging

from dotenv import load_dotenv
load_dotenv()

# Sentry (optionnel — activer via SENTRY_DSN dans .env)
_sentry_dsn = os.getenv("SENTRY_DSN")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    sentry_sdk.init(dsn=_sentry_dsn, integrations=[FlaskIntegration()], traces_sample_rate=0.2)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify
from flask_cors import CORS
from src.api.routes import register_routes
from src.ingestion.run import index_data

app = Flask(__name__)

# CORS : restreint au domaine configuré en prod, ouvert en local
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "*")
CORS(app, origins=_allowed_origins)

register_routes(app)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

# Indexation au démarrage (Gunicorn + dev)
index_data(force_reindex=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
