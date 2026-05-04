# =====================================================
# Rabelia — Quick commands
# =====================================================

.PHONY: help docker-up docker-down index test mcp

# ── Help ──────────────────────────────────────────────
help:
	@echo ""
	@echo "  Rabelia — Available commands"
	@echo "  ────────────────────────────"
	@echo "  make docker-up   Start via Docker (app + Redis)"
	@echo "  make docker-down Stop Docker"
	@echo "  make index       Reindex all files (inside container)"
	@echo "  make test        Run unit tests (inside container)"
	@echo "  make mcp         Start MCP server (Claude Desktop)"
	@echo ""

# ── Docker ────────────────────────────────────────────
docker-up:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "  .env created — fill in LLM/Qdrant/Supabase keys before restarting."; \
		exit 1; \
	fi
	docker compose up --build -d
	@echo ""
	@echo "  App available at: http://localhost:8000"
	@echo "  Redis (internal): redis://redis:6379"
	@echo ""

docker-down:
	docker compose down

# ── Tools ─────────────────────────────────────────────
index:
	docker compose exec app python -c "from src.ingestion.run import index_data; index_data(force_reindex=True)"

test:
	docker compose exec app pytest src/tests/ -v

mcp:
	python src/mcp_server.py
