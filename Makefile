# =====================================================
# Oracle LoreKeeper — Commandes rapides
# =====================================================
# Usage : make <commande>

.PHONY: help docker-up docker-down index test mcp

# ── Aide ─────────────────────────────────────────────
help:
	@echo ""
	@echo "  Rabelia — Commandes disponibles"
	@echo "  ────────────────────────────────"
	@echo "  make docker-up   Lancer via Docker (app + Redis)"
	@echo "  make docker-down Arrêter Docker"
	@echo "  make index       Réindexer tous les fichiers (dans le conteneur)"
	@echo "  make test        Lancer les tests unitaires (dans le conteneur)"
	@echo "  make mcp         Lancer le serveur MCP (Claude Desktop)"
	@echo ""

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
	docker compose exec app python -c "from src.ingestion.run import index_data; index_data(force_reindex=True)"

test:
	docker compose exec app pytest src/test-unitaires/ -v

mcp:
	python src/mcp_server.py
