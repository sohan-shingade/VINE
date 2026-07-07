# VINE — common developer tasks. Run `make help` for the list.
# Every target is also what CI runs, so "green locally" == "green in CI".

.DEFAULT_GOAL := help
.PHONY: help setup fmt lint type test check data train serve docs clean codemap

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install all extras + dev tools
	uv sync --all-extras
	uv run pre-commit install

fmt: ## Auto-format + autofix
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint (no changes)
	uv run ruff check .
	uv run ruff format --check .

type: ## Static type check
	uv run mypy

test: ## Run tests (skip slow/gpu)
	uv run pytest -m "not slow and not gpu"

check: lint type test ## Full local gate — run before every commit/PR

codemap: ## Regenerate docs/codemap/ shards (run after any refactor, same commit)
	uv run python scripts/codemap.py

serve: ## Run the FastAPI inference service locally
	uv run uvicorn vine.d6_serving.app:app --reload

docs: ## Serve the wiki locally at http://127.0.0.1:8000
	uv run mkdocs serve

clean: ## Remove caches and build artifacts
	rm -rf .ruff_cache .mypy_cache .pytest_cache site build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
