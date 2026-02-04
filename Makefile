.PHONY: help install dev-install lint format type-check test clean run-api check-venv

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

check-venv: ## Check if virtual environment is available
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "Using activated venv: $$VIRTUAL_ENV"; \
	elif [ -d .venv ]; then \
		echo "Using .venv directory"; \
	else \
		echo "Error: No virtual environment found."; \
		echo "  Option 1: Activate venv: source .venv/bin/activate"; \
		echo "  Option 2: Use env.sh: source env.sh"; \
		echo "  Option 3: Create venv: uv venv -p 3.12 .venv"; \
		exit 1; \
	fi

install: check-venv ## Install production dependencies
	bash -c 'source env.sh && uv pip install -r requirements.txt'

dev-install: check-venv ## Install development dependencies
	bash -c 'source env.sh && uv pip install -r requirements.txt'
	bash -c 'source env.sh && uv pip install ruff mypy pytest pytest-asyncio pre-commit'
	@if command -v git >/dev/null 2>&1 && [ -d .git ]; then \
		bash -c 'source env.sh && pre-commit install' || echo "Warning: pre-commit install failed (not a git repo or git not available)"; \
	else \
		echo "Skipping pre-commit install (not a git repository)"; \
	fi

lint: check-venv ## Run linter
	@bash -c 'source env.sh && command -v ruff >/dev/null 2>&1 || { echo "Error: ruff not found. Run '\''make dev-install'\'' first."; exit 1; }'
	bash -c 'source env.sh && ruff check .'

lint-fix: check-venv ## Run linter
	@bash -c 'source env.sh && command -v ruff >/dev/null 2>&1 || { echo "Error: ruff not found. Run '\''make dev-install'\'' first."; exit 1; }'
	bash -c 'source env.sh && ruff check . --fix'

format: check-venv ## Format code
	@bash -c 'source env.sh && command -v ruff >/dev/null 2>&1 || { echo "Error: ruff not found. Run '\''make dev-install'\'' first."; exit 1; }'
	bash -c 'source env.sh && ruff format .'

type-check: check-venv ## Run type checker
	@bash -c 'source env.sh && command -v mypy >/dev/null 2>&1 || { echo "Error: mypy not found. Run '\''make dev-install'\'' first."; exit 1; }'
	bash -c 'source env.sh && mypy api lib'

test: check-venv ## Run tests
	@bash -c 'source env.sh && command -v pytest >/dev/null 2>&1 || { echo "Error: pytest not found. Run '\''make dev-install'\'' first."; exit 1; }'
	bash -c 'source env.sh && pytest' || { exit_code=$$?; if [ $$exit_code -eq 5 ]; then echo "No tests found (this is OK for a new project)"; exit 0; else exit $$exit_code; fi; }

check: lint type-check test ## Run all checks (lint, type-check, test)

clean: ## Clean cache and temporary files
	find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache

run-api: check-venv ## Run the FastAPI server
	bash -c 'source env.sh && python api/main.py'

apply-migrations: check-venv ## Run Alembic migrations (requires DATABASE_URL in .env)
	bash -c 'source env.sh && alembic upgrade head'

migrate-legacy: check-venv ## Migrate legacy file data into Postgres (requires .env)
	bash -c 'source env.sh && python scripts/migrate_to_db.py'

db-setup: apply-migrations migrate-legacy ## Apply schema migrations then import legacy data
