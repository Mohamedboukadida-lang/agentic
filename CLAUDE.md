# ragent

Retrieval core of an agentic RAG assistant over AWS documentation: ingestion, a
pgvector store and hybrid retrieval, in Python. Public repo: never commit secrets, real
data, or fetched documentation (`data/raw/` is git-ignored).

The agent, guardrails, eval suite and API are not in the repo yet. `docs/PENDING.md`
lists what is missing and which files change when each part lands. `docs/DESIGN.md` and
`docs/PLAN.md` describe the whole project.

## Commands

| Task | Command |
|---|---|
| Install | `make setup && source .venv/bin/activate` |
| Test (unit, no services) | `pytest -q` |
| Test (one file / one case) | `pytest -q tests/unit/test_retrieval.py` / `pytest -q -k name` |
| Test (integration) | `make up && make test-integration` |
| Lint | `ruff check . && ruff format --check .` |
| Format | `make format` |
| Offline demo | `make demo-offline` |
| Migrations | `make migrate` (applies `db/migrations/*.sql` in order) |

CI (`.github/workflows/ci.yml`) runs lint, unit tests, an offline search smoke test,
and the integration tests against a pgvector service. A change is acceptable only when
lint and unit tests pass locally.

Runtime: Python >= 3.11 (CI uses 3.12). Package manager: pip, editable install.

## Layout

```
src/ragent/config.py     all settings; the only place that reads RAGENT_* variables
src/ragent/models.py     plain dataclasses passed between modules
src/ragent/factory.py    builds store, embedder, chat, retriever from Settings
src/ragent/cli.py        migrate, ingest, chunk-stats, search
src/ragent/ingest/       loaders, chunking, pipeline
src/ragent/store/        ChunkStore protocol, pgvector and in-memory implementations
src/ragent/retrieval/    retriever, RRF fusion, rerankers
src/ragent/llm/          Embedder/ChatModel protocols, Ollama and fake implementations
tests/unit/              no services; tests/integration/ needs PostgreSQL
```

## Conventions

- Everything external sits behind a protocol (`llm/base.py`, `store/base.py`) with a
  fake implementation, so unit tests need no model and no database.
- New settings go in `config.py` as a typed field; nothing else reads the environment.
- Wire new parts in `factory.py`; entry points never construct them directly.
- Tests for new logic before moving on. Unit tests use the `offline` fixture in
  `tests/conftest.py`. Tests that need PostgreSQL carry `@pytest.mark.integration`.
- Schema changes are a new numbered file in `db/migrations/`; never edit an applied one.
- Record choices in `docs/DECISIONS.md` and bugs that cost time in `docs/WHAT_BROKE.md`.
- Line length 100, ruff rules `E,F,I,B,UP,SIM`.

## Hazards

- Changing chunking settings or the embedding model re-ingests every document.
  Changing `embed_dim` needs a new migration.
- `make models` downloads several GB.
- The database credentials in `docker-compose.yml` and `.env.example` are local
  development defaults, not secrets. Do not reuse them anywhere reachable.
