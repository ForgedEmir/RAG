# =====================================================
# Oracle LoreKeeper — Commandes rapides
# =====================================================
# Usage : make <commande>

.PHONY: help setup install run docker-up docker-down index test mcp

# ── Aide ─────────────────────────────────────────────
help:
	@echo ""
	@echo "  Oracle LoreKeeper — Commandes disponibles"
	@echo "  ─────────────────────────────────────────"
	@echo "  make setup       Premier lancement complet (install + .env + index)"
	@echo "  make install     Installer les dépendances Python"
	@echo "  make run         Lancer l'app en local (http://localhost:8000)"
	@echo "  make docker-up   Lancer via Docker (app + Redis)"
	@echo "  make docker-down Arrêter Docker"
	@echo "  make index       Réindexer tous les fichiers lore"
	@echo "  make test        Lancer les tests unitaires"
	@echo "  make mcp         Lancer le serveur MCP (Claude Desktop)"
	@echo ""

# ── Premier lancement ────────────────────────────────
setup:
	@echo ">>> Vérification du fichier .env..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "  .env créé depuis .env.example — remplis les clés API !"; \
		echo "  Ouvre .env et ajoute au minimum LLM_API_KEY, QDRANT_URL, SUPABASE_URL."; \
		exit 1; \
	fi
	@echo ">>> Installation des dépendances..."
	pip install -r requirements.txt
	@echo ">>> Indexation des fichiers lore..."
	python -c "from src.ingestion.run import index_data; index_data(force_reindex=False)"
	@echo ""
	@echo "  Setup terminé. Lance l'app avec : make run"
	@echo ""

# ── Développement ─────────────────────────────────────
install:
	pip install -r requirements.txt

run:
	python main.py

# ── Docker ────────────────────────────────────────────
docker-up:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "  .env créé — remplis les clés LLM/Qdrant/Supabase avant de relancer."; \
		exit 1; \
	fi
	docker compose up --build -d
	@echo ""
	@echo "  App disponible sur : http://localhost:8000"
	@echo "  Redis (interne)   : redis://redis:6379"
	@echo ""

docker-down:
	docker compose down

# ── Outils ────────────────────────────────────────────
index:
	python -c "from src.ingestion.run import index_data; index_data(force_reindex=True)"

test:
	pytest src/test-unitaires/ -v

mcp:
	python src/mcp_server.py
