.DEFAULT_GOAL := help
PY ?= python3
Q ?= What is the default visibility timeout for an SQS queue?
CORPUS ?= data/raw

.PHONY: help setup models up down migrate ingest-sample ingest fetch ask search \
        test test-integration lint format chunk-stats demo-offline

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-18s %s\n", $$1, $$2}'

setup: ## Create .venv and install the package with dev tools
	$(PY) -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@test -f .env || cp .env.example .env
	@echo "Run: source .venv/bin/activate"

models: ## Pull the default Ollama models
	ollama pull llama3.1:8b
	ollama pull nomic-embed-text

up: ## Start PostgreSQL with pgvector
	docker compose up -d --wait db

down: ## Stop containers (data volume is kept)
	docker compose down

migrate: ## Apply db/migrations
	ragent migrate

ingest-sample: ## Ingest the small sample corpus
	ragent ingest data/sample

fetch: ## Download the pages listed in data/sources.yaml into data/raw
	$(PY) scripts/fetch_docs.py

ingest: ## Ingest CORPUS (default data/raw)
	ragent ingest $(CORPUS)

ask: ## Ask the agent:  make ask Q="..."
	ragent ask "$(Q)"

search: ## Retrieval only:  make search Q="..."
	ragent search "$(Q)"

test: ## Unit tests (no Ollama, no database)
	pytest -q

test-integration: ## Tests against the running PostgreSQL
	RAGENT_DATABASE_URL=postgresql://ragent:ragent@localhost:5432/ragent pytest -q -m integration

lint: ## Lint and check formatting
	ruff check .
	ruff format --check .

format: ## Format the code
	ruff format .
	ruff check --fix .

chunk-stats: ## Compare chunking settings on CORPUS
	ragent chunk-stats $(CORPUS)

demo-offline: ## Full path with no Ollama and no database
	ragent ask "$(Q)" --offline data/sample
