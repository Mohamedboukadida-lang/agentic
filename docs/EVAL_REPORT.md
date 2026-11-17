# Eval report

Every number here needs four facts next to it: the corpus, the number of questions, the
models, and the date. A number without them cannot be compared with anything.

## 0. Plumbing check (came with the scaffold)

This is **not a result**. It was run with the fake embedder (hashed bag of words) and the
in-memory store on the 6-document sample corpus, to show that the eval pipeline works.
Hit rate is at the ceiling because the corpus is tiny and the questions share words with
the documents, which is exactly the "eval set too easy" problem to avoid in your own set.

Corpus: `data/sample` (6 documents, 39 chunks). Questions: 21 answerable of 24 in
`evals/dataset.jsonl`. Embedder: `FakeEmbedder(256)`. Date: 2026-11-10.

| Mode | Reranker | Hit rate@5 | Recall@5 | MRR |
| --- | --- | --- | --- | --- |
| vector | none | 1.000 | 0.976 | 0.938 |
| keyword | none | 0.952 | 0.929 | 0.905 |
| hybrid | none | 1.000 | 0.976 | 0.937 |
| hybrid | lexical | 1.000 | 0.976 | 0.937 |

Reproduce: `RAGENT_RERANKER=none ragent eval retrieval --offline data/sample --mode keyword`

## 1. Chunk statistics (day 3)

Paste the output of `make chunk-stats` here, plus how often each strategy cut a list,
table or code block in the 10 boundaries you read.

## 2. Baseline on the real corpus (day 6)

Corpus: _N documents, N chunks._ Questions: _N (dev split), dataset tag `eval-v1`._
Embedder: _model._ Date: _..._

| Mode | Reranker | Hit rate@5 | Recall@5 | MRR |
| --- | --- | --- | --- | --- |
| vector | none | | | |
| keyword | none | | | |
| hybrid | none | | | |

Misses and what they have in common:

## 3. Experiment log

One row per change. Change one thing at a time.

| Date | Change | Hit rate@5 before -> after | MRR before -> after | Other metric | Why it moved |
| --- | --- | --- | --- | --- | --- |
| | | | | | |

## 4. Answer quality (days 7 to 8)

Chat model: _..._ Questions: _N._ Date: _..._

| System | Refusal accuracy | Point coverage | Citation precision | Faithfulness | p50 / p95 latency |
| --- | --- | --- | --- | --- | --- |
| Single-shot RAG | | | | | |
| Agent | | | | | |

Judge agreement with hand labels (10 answers): _N of 10._

## 5. Prompt injection (day 10)

| Scanner | Attack success rate | Poisoned questions | Honest chunks dropped in the real corpus |
| --- | --- | --- | --- |
| off | | | n/a |
| on | | | |

Phrasings the scanner misses:

## 6. Failure analysis (day 11)

| Question id | Category | What happened | Fixed? |
| --- | --- | --- | --- |
| | retrieval miss / bad ranking / ignored context / wrong refusal / wrong citation | | |

## 7. Held-out test split (days 11 and 14)

Run only twice. If dev and test differ a lot, you tuned to the dev questions.

| Date | Hit rate@5 dev | Hit rate@5 test | Coverage dev | Coverage test |
| --- | --- | --- | --- | --- |
| | | | | |

## Dataset changes

Note every change to the eval set after `eval-v1` here (question id, what changed, why).
