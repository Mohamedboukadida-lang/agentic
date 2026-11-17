# ragent

Agentic RAG assistant over AWS documentation, in Python: ingestion, a pgvector store,
hybrid retrieval, a tool-calling agent loop, guardrails and an eval suite. Public repo: never commit secrets, real
data, or fetched documentation (`data/raw/` is git-ignored).

The HTTP API is not in the repo yet. `docs/PENDING.md`
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
| Offline eval (the CI gate) | `make eval-offline` |
| Migrations | `make migrate` (applies `db/migrations/*.sql` in order) |

CI (`.github/workflows/ci.yml`) runs lint, unit tests, an offline agent smoke test,
dataset validation, the offline retrieval eval gate (hit rate >= 0.90), and the integration tests against a pgvector service. A change is acceptable only when
lint and unit tests pass locally.

Runtime: Python >= 3.11 (CI uses 3.12). Package manager: pip, editable install.

## Layout

```
src/ragent/config.py     all settings; the only place that reads RAGENT_* variables
src/ragent/models.py     plain dataclasses passed between modules
src/ragent/factory.py    builds store, embedder, chat, retriever, agent from Settings
src/ragent/cli.py        migrate, ingest, chunk-stats, search, ask, eval
src/ragent/ingest/       loaders, chunking, pipeline
src/ragent/store/        ChunkStore protocol, pgvector and in-memory implementations
src/ragent/retrieval/    retriever, RRF fusion, rerankers
src/ragent/llm/          Embedder/ChatModel protocols, Ollama and fake implementations
src/ragent/agent/        agent loop, tools, prompts, single-shot RAG baseline
src/ragent/guardrails/   input checks, injection scan, citation validation
src/ragent/observability/ trace ids and timing
src/ragent/eval/         dataset model, metrics, runners, reports
evals/                   labelled questions (dataset.jsonl, injection.jsonl), poisoned fixture
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
- Eval labels point at content (`source` + `contains` phrases), not chunk ids. Once a
  dataset is tagged, do not change its questions; add new ids instead.
- Never lower `--min-hit-rate` in CI to get green; raise it when an experiment lands.
- Line length 100, ruff rules `E,F,I,B,UP,SIM`.

## Hazards

- Changing chunking settings or the embedding model re-ingests every document.
  Changing `embed_dim` needs a new migration.
- `evals/poisoned/` holds a deliberately malicious document for the injection tests.
  Never ingest it into a store you use for real questions.
- `make models` downloads several GB.
- The database credentials in `docker-compose.yml` and `.env.example` are local
  development defaults, not secrets. Do not reuse them anywhere reachable.
