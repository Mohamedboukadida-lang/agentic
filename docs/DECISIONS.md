# Decisions

One entry per choice: what, the alternatives, the reason. Newest at the bottom.

The first entries came with the scaffold. Read each one, check that you agree, and
rewrite it in your own words. If you change your mind, add a new entry; do not delete
the old one.

---

## 1. PostgreSQL with pgvector, not a dedicated vector database

- **Alternatives:** Qdrant, Chroma, FAISS files.
- **Reason:** One database gives vectors, full-text search, metadata and transactions.
  Hybrid search needs both indexes over the same rows. PostgreSQL is also what most
  backend teams already run.
- **Cost:** Tuning is manual, and very large corpora need more care than a purpose-built
  engine.

## 2. Hybrid retrieval merged with reciprocal rank fusion

- **Alternatives:** vector only; weighted sum of normalised scores.
- **Reason:** Embeddings miss exact identifiers and limits; keyword search misses
  paraphrases. RRF uses ranks only, so cosine similarity and `ts_rank_cd` never need to
  be put on one scale.
- **To verify:** day 6 measures vector, keyword and hybrid on the real corpus.

## 3. Keyword query ORs the content words

- **Alternatives:** `websearch_to_tsquery` or `plainto_tsquery`, which AND the terms.
- **Reason:** A natural-language question rarely has all its words in one passage, so an
  AND query returns nothing. OR plus ranking by `ts_rank_cd` returns the best partial
  matches.

## 4. A hand-written agent loop, not a framework

- **Alternatives:** LangGraph, LlamaIndex agents.
- **Reason:** The loop is about 120 lines and every stop rule is explicit and tested.
  Nothing is hidden when debugging.
- **Revisit:** day 9 ports it to LangGraph on a branch for a measured comparison.

## 5. Refuse when the answer has no valid citation

- **Alternatives:** return the uncited answer with a warning.
- **Reason:** An uncited answer cannot be checked and is the most likely place for a
  hallucination. A refusal is safe, and it is scored as correct for unanswerable questions.
- **Cost:** Some correct answers are lost when the model forgets to cite. Measure it:
  count `stop_reason = no_citations` on answerable questions.

## 6. Eval labels point at content, not chunk ids

- **Alternatives:** label the exact chunk id per question.
- **Reason:** Chunk ids change whenever chunking changes, and chunking is the first thing
  to experiment with. `source` plus `contains` phrases survive re-chunking.
- **Cost:** A phrase can match a chunk that is not really the evidence. Keep phrases
  specific.

## 7. Offline fake providers for tests and CI

- **Alternatives:** call a real model in CI; mock at the HTTP layer.
- **Reason:** CI must be fast, free and deterministic. The fake embedder is a hashed bag
  of words, enough to exercise the whole retrieval path.
- **Cost:** CI numbers say nothing about real quality. Real-corpus numbers come from
  local runs and are reported separately.

## 8. Ollama with llama3.1:8b and nomic-embed-text as defaults

- **Alternatives:** hosted APIs (better answers, cost money); other local models.
- **Reason:** Free, private, works offline, and both models are widely used. The provider
  sits behind two protocols, so switching is one new class.
- **To verify:** day 1. If tool calling is unreliable, try `qwen2.5:7b` and record it.

---

<!-- Add your own from here.

## N. Title
- **Alternatives:**
- **Reason:**
- **Cost / to verify:**
-->
