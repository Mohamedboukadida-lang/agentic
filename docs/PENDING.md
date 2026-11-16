# Pending: what has not been pushed yet

This repository was pushed in parts. Parts 1 (retrieval core) and 2 (guardrails and
agent) are on `main`. The rest
exists in the original project archive (`agentic-rag.zip`) and lands in the order below.
Tick a part when it is merged, and delete this file when the list is empty.

Paths are relative to the repository root and are the same in the archive.

## Part 2: guardrails and agent (done)

- [x] Add `src/ragent/guardrails/` (`input.py`, `injection.py`, `output.py`)
- [x] Add `src/ragent/observability/` (`tracing.py`)
- [x] Add `src/ragent/agent/` (`loop.py`, `tools.py`, `parsing.py`, `prompts.py`, `single_shot.py`)
- [x] Add `tests/unit/test_guardrails.py`, `tests/unit/test_agent.py`
- [x] Add `evals/poisoned/kinesis.md` (the agent tests read it through `tests/conftest.py`)
- [x] Restore in `src/ragent/factory.py`: `Toolbox`, `Agent`, `SingleShotRAG` imports, the
      three `Container` fields and their wiring in `build_container`
- [x] Restore in `src/ragent/cli.py`: `cmd_ask`, the `ask` subparser, `import json`
- [x] Restore in `Makefile`: `ask` target; point `demo-offline` back at `ragent ask`

## Part 3: evaluation suite

- [ ] Add `src/ragent/eval/` (`dataset.py`, `metrics.py`, `runner.py`, `report.py`)
- [ ] Add `evals/README.md`, `evals/dataset.jsonl`, `evals/injection.jsonl`
- [ ] Add `tests/unit/test_eval.py`
- [ ] Add `docs/EVAL_REPORT.md`
- [ ] Restore in `src/ragent/cli.py`: `cmd_eval`, the `eval` subparser, `load_dataset`
      import, `DEFAULT_DATASET`
- [ ] Restore in `Makefile`: `eval`, `eval-answers`, `eval-injection`, `eval-offline`
- [ ] Restore in `.github/workflows/ci.yml`: the "Validate eval datasets" step, the
      "Offline retrieval eval" gate (`--min-hit-rate 0.90`) and the `eval-report`
      artifact upload. Drop the "Offline agent smoke test" step only if the gate and answer eval cover it.

## Part 4: HTTP API and container image

- [ ] Add `src/ragent/api/` (`app.py`)
- [ ] Add `tests/unit/test_api.py`
- [ ] Add `Dockerfile`, `.dockerignore`
- [ ] Restore in `pyproject.toml`: `fastapi>=0.110`, `uvicorn[standard]>=0.29`
- [ ] Restore in `src/ragent/cli.py`: `cmd_serve`, the `serve` subparser
- [ ] Restore in `Makefile`: `serve` target
- [ ] Restore in `docker-compose.yml`: the `api` service and its header comment line

## After the last part

- [ ] Replace `README.md` with the full version from the archive
- [ ] Keep `permissions: contents: read` in `ci.yml` (added in part 1, not in the archive)
- [ ] Update `CLAUDE.md` (commands, layout) for the full project
- [ ] Delete this file
- [ ] Check: `ruff check . && ruff format --check . && pytest -q` gives 80 passed
      (63 after part 2), and
      `ragent eval retrieval --offline data/sample --min-hit-rate 0.90` exits 0

## Not in the archive (your own work, per docs/PLAN.md)

- [ ] Licence file (day 12)
- [ ] CI badge in the README (day 12)
- [ ] Real corpus, your own eval questions and measured results (days 2 to 11)
