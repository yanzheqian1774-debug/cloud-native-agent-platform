.DEFAULT_GOAL := help

.PHONY: help setup sync lock format format-check lint test check clean tree status console-e2e frontend-check agent-workbench-e2e skill-mcp-workbench-e2e

help:
	@echo "Cloud Native Multi-Agent Platform"
	@echo ""
	@echo "Available commands:"
	@echo "  make setup         Install dependencies and Git hooks"
	@echo "  make sync          Sync dependencies from uv.lock"
	@echo "  make lock          Update the dependency lockfile"
	@echo "  make format        Format Python code"
	@echo "  make format-check  Verify Python formatting"
	@echo "  make lint          Run Ruff lint checks"
	@echo "  make test          Run pytest"
	@echo "  make check         Run all local quality checks"
	@echo "  make clean         Remove local Python caches"
	@echo "  make tree          Show project structure"
	@echo "  make status        Show Git status"

setup:
	uv sync
	uv run pre-commit install

sync:
	uv sync --frozen

lock:
	uv lock

format:
	uv run ruff check . --fix
	uv run ruff format .

format-check:
	uv run ruff format --check .

lint:
	uv run ruff check .

test:
	uv run pytest

check: lint format-check test
	@echo "All local quality checks passed."

frontend-check:
	cd console/frontend && npm run lint && npm run build

agent-workbench-e2e:
	cd console/frontend && npm run test:e2e

skill-mcp-workbench-e2e:
	cd console/frontend && npx playwright test tests/e2e/skill-mcp-workbench.spec.ts

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

tree:
	tree -a -L 3 -I ".git|.venv|__pycache__|.pytest_cache|.ruff_cache"

status:
	git status

console-e2e:
	./scripts/e2e/console-real-workflow.sh
