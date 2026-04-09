.PHONY: setup dev backend frontend test lint clean help

PYTHON   := python3
VENV     := .venv
PIP      := $(VENV)/bin/pip
PYBIN    := $(VENV)/bin
NODE_DIR := frontend

# ── Setup ────────────────────────────────────────────────────────────────────

setup: ## One-time setup: create venv, install all deps, install frontend packages
	@bash setup.sh

# ── Dev servers ──────────────────────────────────────────────────────────────

dev: ## Start backend + frontend together (Ctrl-C stops both)
	@echo "Starting LabelForge — backend :8000, frontend :5173"
	@trap 'kill 0' INT; \
		$(PYBIN)/uvicorn backend.main:app --reload --port 8000 & \
		(cd $(NODE_DIR) && npm run dev) & \
		wait

backend: ## Start backend only
	$(PYBIN)/uvicorn backend.main:app --reload --port 8000

frontend: ## Start frontend only
	cd $(NODE_DIR) && npm run dev

# ── Quality ───────────────────────────────────────────────────────────────────

test: ## Run pytest
	$(PYBIN)/pytest

test-cov: ## Run pytest with coverage
	$(PYBIN)/pytest --cov=labelforge --cov-report=term-missing

lint: ## Ruff + mypy
	$(PYBIN)/ruff check labelforge tests backend
	$(PYBIN)/mypy labelforge backend

format: ## Auto-fix lint issues
	$(PYBIN)/ruff check --fix labelforge tests backend

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean: ## Remove venv, node_modules, pycache, DB
	rm -rf $(VENV)
	rm -rf $(NODE_DIR)/node_modules
	rm -f backend/labelforge.db
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	@echo "Cleaned."

# ── Docker ───────────────────────────────────────────────────────────────────

docker-build: ## Build Docker image
	docker compose build

docker-up: ## Start app in Docker (http://localhost:8000)
	docker compose up -d

docker-down: ## Stop Docker containers
	docker compose down

docker-logs: ## Tail Docker logs
	docker compose logs -f

docker-clean: ## Stop containers and remove volumes (clears DB)
	docker compose down -v

# ── Help ──────────────────────────────────────────────────────────────────────

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
