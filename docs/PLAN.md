# 14-day plan

About 1.5 to 2 hours per day. The repo starts with a working baseline, so your time goes
to understanding it, feeding it real documents, measuring it and improving it.

Rules for every day:

- One change at a time, measured before and after. Log it in `EVAL_REPORT.md`.
- Add an entry to `DECISIONS.md` for every choice and to `WHAT_BROKE.md` for every bug
  that cost you more than 15 minutes.
- Commit at the end of each day with a message that says what changed and why.

If you fall behind: drop day 9 first, then the cross-encoder reranker, then streaming.
Never drop days 5 to 7 or day 11.

---

## Day 1: setup and first answer

- [ ] Install Docker and Ollama. Check `docker --version` and `ollama --version`.
- [ ] `make setup && source .venv/bin/activate`
- [ ] `make test` and `make demo-offline` (no services needed)
- [ ] `make models` (large download; start it early)
- [ ] `make up && make migrate && make ingest-sample`
- [ ] `make ask Q="What is the default visibility timeout for an SQS queue?"`
- [ ] Run it again with `ragent -v ask "..."` and read the trace line.
- [ ] Follow that one question through the code: `cli.cmd_ask` -> `agent/loop.py` ->
      `agent/tools.py` -> `retrieval/retriever.py` -> `store/pgvector.py`.

**Exit check:** an answer with a citation on screen. You can say in two sentences what
each of the five files above does. First entry in `DECISIONS.md` (which chat model, why).

**If tool calling fails** (the model answers without searching, or prints JSON): try
`RAGENT_CHAT_MODEL=qwen2.5:7b`. Note what happened in `WHAT_BROKE.md`.

## Day 2: real corpus

- [ ] Pick 15 to 25 AWS documentation pages for the services on your exam. Prefer pages
      with concrete limits and behaviours over marketing overviews.
- [ ] Open every URL by hand, then add it to `data/sources.yaml`.
- [ ] `make fetch`
- [ ] Inspect what the loader produces:
      `python -c "from pathlib import Path; from ragent.ingest.loaders import load_path; print(load_path(Path('data/raw/sqs-visibility.html')).text[:3000])"`
- [ ] Fix loader problems in `ingest/loaders.py` (leftover menus, feedback widgets,
      duplicated text). Add a unit test for each fix.
- [ ] `make ingest`

**Exit check:** corpus ingested. You have read 5 random chunks in `psql` and they are
clean prose:
`SELECT d.source, c.section, left(c.content, 300) FROM chunks c JOIN documents d ON d.id = c.document_id ORDER BY random() LIMIT 5;`

## Day 3: chunking

- [ ] `make chunk-stats` and paste the table into `EVAL_REPORT.md`.
- [ ] For each strategy, read 10 chunk boundaries. Count how often a list, table or code
      block is cut in half.
- [ ] Read `ingest/chunking.py`. Decide whether very small sections should be merged
      with their neighbour (not implemented; a good first feature).
- [ ] Choose a default and record why in `DECISIONS.md`. You will test the choice with
      numbers on day 7.

**Exit check:** chunk statistics table and a chosen default with a reason.

## Day 4: retrieval internals

- [ ] In `psql`, run a keyword query by hand:
      `SELECT d.source, c.ordinal, ts_rank_cd(c.tsv, q) FROM chunks c JOIN documents d ON d.id = c.document_id, to_tsquery('english', 'visibility | timeout') q WHERE c.tsv @@ q ORDER BY 3 DESC LIMIT 5;`
- [ ] `EXPLAIN ANALYZE` that query and a vector query. Is the GIN index used? Is the HNSW
      index used? (On a tiny table PostgreSQL may prefer a sequential scan. Find out why.)
- [ ] For 5 questions compare `ragent search "..." --mode vector`, `--mode keyword` and
      the default. Find one question where keyword wins and one where vector wins.
- [ ] Read `retrieval/fusion.py` and work one RRF example by hand.
- [ ] Try `RAGENT_RERANKER=llm ragent search "..."` and time it.

**Exit check:** you can explain reciprocal rank fusion on a whiteboard and show one
question where keyword search wins.

## Day 5: eval set

- [ ] Read `evals/README.md`.
- [ ] Write 40 questions on your corpus into `evals/dataset.jsonl`: at least 8 of each
      type and 8 unanswerable. Mark about 10 as `"split": "test"`.
- [ ] `ragent eval validate`
- [ ] Check every label matches a chunk (adapt the test
      `test_shipped_dataset_labels_match_the_sample_corpus` to your corpus).
- [ ] Commit and tag: `git tag eval-v1`.

**Exit check:** validated, committed, tagged. From now on the questions do not change.

## Day 6: baseline

- [ ] `ragent eval retrieval --split dev --mode vector`
- [ ] `ragent eval retrieval --split dev --mode keyword`
- [ ] `ragent eval retrieval --split dev` (hybrid)
- [ ] Record all three in the experiment log. Read every miss.
- [ ] Decide the CI story: CI runs the offline eval on the sample corpus (fast, no
      model). Your real-corpus numbers come from local runs. Say so in the README.
- [ ] Set your local floor: baseline hit rate minus 5 points.

**Exit check:** baseline row in `EVAL_REPORT.md`, with misses listed.

## Day 7: experiments

One at a time, each logged with before and after:

- [ ] Chunk size 300 vs 500 vs 800 (re-ingest between runs)
- [ ] Fixed vs structure-aware chunking
- [ ] Reranker none vs lexical vs llm
- [ ] top-k 3 vs 5 vs 8
- [ ] First answer-level run: `ragent eval answers --split dev`
- [ ] Use the unanswerable questions to tune `RAGENT_MIN_RELEVANCE`.

**Exit check:** at least 3 experiment rows. One sentence per row on why the number moved.

## Day 8: agent

- [ ] Read `agent/loop.py` and `tests/unit/test_agent.py` line by line.
- [ ] Add 10 comparison and multi-step questions to the dataset (new ids, note the
      addition in `EVAL_REPORT.md`; tag `eval-v2`).
- [ ] `ragent eval answers --single-shot` vs `ragent eval answers` on those questions.
- [ ] Look at traces of 5 agent runs. Does it search twice when it should? Does it use
      `compare_services`?
- [ ] Improve `agent/prompts.py` once, measure again.

**Exit check:** a table of single-shot versus agent on the new questions.

## Day 9: agent, part 2 (optional, first to drop)

Pick one:

- [ ] Port the loop to LangGraph on a branch, run the same eval, compare code size,
      latency and results. Merge only if it is clearly better. List LangGraph on your CV
      only if you merge it.
- [ ] Or improve `compare_services` (for example, search each service with a source
      filter) and add a new stop rule with a test.

**Exit check:** decision recorded with the reason.

## Day 10: guardrails

- [ ] `ragent ingest evals/poisoned`
- [ ] `RAGENT_INJECTION_SCAN=false ragent eval answers --dataset evals/injection.jsonl`
- [ ] `RAGENT_INJECTION_SCAN=true ragent eval answers --dataset evals/injection.jsonl`
- [ ] Write 5 more poisoned documents with different phrasings, including one the
      scanner misses. Add questions for them.
- [ ] Extend `guardrails/injection.py`, with a test for each new pattern and a test that
      ordinary documentation still passes.
- [ ] Run the scanner over your whole real corpus. How many honest chunks does it drop?

**Exit check:** two attack success numbers (off, on) and a false-positive count.

## Day 11: failure analysis

- [ ] Full run on dev, then the first run on the test split.
- [ ] Take the 10 worst failures. Label each: retrieval miss, bad ranking, model ignored
      context, wrong refusal, wrong citation.
- [ ] Fix the largest group. Measure.
- [ ] If you use `--judge`, hand-check 10 judged answers and report the agreement rate.

**Exit check:** a failure table and one fix with a measured effect.

## Day 12: packaging

- [ ] `docker compose --profile api up -d --build`, then `curl localhost:8000/health`
- [ ] Push to GitHub. Get both CI jobs green. Add the badge to the README.
- [ ] Clone into a fresh folder and follow your own README. Fix what is missing.
- [ ] Find the slowest request in the traces. Where does the time go?
- [ ] Add a licence file.

**Exit check:** a fresh clone runs with three commands. Green CI.

## Day 13: README

- [ ] Rewrite `README.md`: what it is, architecture diagram, results table with corpus,
      question count, model and date, failure analysis, limits, how to run.
- [ ] Add "what I would change at 100x the corpus" (index build time, filtering by
      service, caching, connection pool, hosted model cost per query).

**Exit check:** someone can understand the project in 3 minutes without running it.

## Day 14: demo and release

- [ ] Record a 2-minute demo: one factual question, one comparison, one refusal, one
      blocked injection, then the eval table.
- [ ] `git tag v1.0`
- [ ] Update the CV bullet with your measured numbers. Use only numbers from
      `EVAL_REPORT.md`.
- [ ] Practise the eight interview questions in the plan document out loud.

**Exit check:** public repo, tagged, with a demo link.

---

## Stretch goals

- Deploy on AWS: the API on ECS Fargate or Lambda, RDS PostgreSQL with pgvector, Bedrock
  for the model (add a `BedrockChat` next to `OllamaChat`). This ties the project to the
  ingestion platform project.
- Cross-encoder reranker (`bge-reranker-base`).
- Answer cache keyed by question and corpus version.
- Token streaming of the final answer.
- Connection pool (`psycopg_pool`).
