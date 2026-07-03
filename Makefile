.PHONY: help check-venv install install-qwen install-vibevoice install-all dev-install lock lock-check lint lint-fix format type-check test check clean run-api db-up db-down apply-migrations db-setup download-models start

BACKEND ?= qwen
PYTHON ?= python3.12

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

check-venv: ## Check if virtual environment is available
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "Using activated venv: $$VIRTUAL_ENV"; \
	elif [ -d .venv ]; then \
		echo "Using .venv directory"; \
	else \
		echo "Error: No virtual environment found."; \
		echo "  Run: make install   (uv sync creates .venv)"; \
		exit 1; \
	fi

# Note: `uv sync` installs exactly the locked set for the chosen extras and
# removes anything else (not additive like pip install): running `make install`
# after `make install-qwen` uninstalls the qwen extra.
install: ## Install base dependencies (no backends, no dev tools)
	uv sync --no-dev

install-qwen: ## Install base + Qwen backend dependencies
	uv sync --no-dev --extra qwen

install-vibevoice: ## Install base + VibeVoice backend dependencies
	uv sync --no-dev --extra vibevoice

install-all: ## Install base + all backend dependencies
	uv sync --no-dev --all-extras

dev-install: ## Install dev tools (ruff, mypy, pytest, pre-commit) and hooks
	uv sync
	@if command -v git >/dev/null 2>&1 && [ -d .git ]; then \
		bash -c 'source env.sh && pre-commit install' || echo "Warning: pre-commit install failed"; \
	fi

lock: ## Re-resolve uv.lock after changing pyproject.toml
	uv lock

lock-check: ## Verify uv.lock is in sync with pyproject.toml
	uv lock --check

lint: check-venv ## Run linter
	@bash -c 'source env.sh && command -v ruff >/dev/null 2>&1 || { echo "Error: ruff not found. Run make dev-install first."; exit 1; }'
	bash -c 'source env.sh && ruff check api lib services scripts examples tests'

lint-fix: check-venv ## Run linter with automatic fixes
	@bash -c 'source env.sh && command -v ruff >/dev/null 2>&1 || { echo "Error: ruff not found. Run make dev-install first."; exit 1; }'
	bash -c 'source env.sh && ruff check api lib services scripts examples tests --fix'

format: check-venv ## Format code
	@bash -c 'source env.sh && command -v ruff >/dev/null 2>&1 || { echo "Error: ruff not found. Run make dev-install first."; exit 1; }'
	bash -c 'source env.sh && ruff format api lib services scripts examples tests'

type-check: check-venv ## Run type checker
	@bash -c 'source env.sh && command -v mypy >/dev/null 2>&1 || { echo "Error: mypy not found. Run make dev-install first."; exit 1; }'
	bash -c 'source env.sh && mypy api lib services'

test: check-venv ## Run tests
	@bash -c 'source env.sh && command -v pytest >/dev/null 2>&1 || { echo "Error: pytest not found. Run make dev-install first."; exit 1; }'
	bash -c 'source env.sh && pytest'

check: lint type-check test ## Run all checks

clean: ## Clean cache and temporary files
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

run-api: check-venv ## Run the FastAPI server
	bash -c 'source env.sh && python api/main.py'

db-up: ## Start local Postgres via Docker Compose
	docker compose up -d db

db-down: ## Stop local Postgres
	docker compose down

apply-migrations: check-venv ## Run Alembic migrations, requires DATABASE_URL
	bash -c 'source env.sh && alembic upgrade head'

db-setup: apply-migrations ## Apply schema migrations

download-models: check-venv ## Pre-download Hugging Face models; set BACKEND=qwen|vibevoice|all
	bash -c 'source env.sh && python scripts/download_models.py --backend $(BACKEND)'

start: ## One-command setup, model download, DB setup, and API start
	./scripts/start.sh --backend $(BACKEND)
