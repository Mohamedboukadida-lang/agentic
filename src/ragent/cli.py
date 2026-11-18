"""Command line interface.  Run `ragent --help`.

    ragent migrate                         apply db/migrations to PostgreSQL
    ragent ingest data/sample              load, chunk, embed and store a folder
    ragent chunk-stats data/sample         compare chunking settings without storing
    ragent search "visibility timeout"     show retrieval with per-stage ranks
    ragent ask "..."                       ask the agent (--single-shot for plain RAG)
    ragent eval validate                   check the dataset file
    ragent eval retrieval                  hit rate, recall, MRR  (no chat model needed)
    ragent eval answers                    refusal accuracy, coverage, citations, latency
    ragent serve                           start the HTTP API

Add --offline DIR to search, ask and eval to run with fake providers and an in-memory
store filled from DIR. No Ollama and no database needed.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ragent.config import Settings
from ragent.eval.dataset import load_dataset
from ragent.factory import Container, build_container, build_offline_container

DEFAULT_DATASET = Path("evals/dataset.jsonl")


def _container(args: argparse.Namespace, **overrides: object) -> Container:
    if getattr(args, "offline", None):
        return build_offline_container(Path(args.offline), **overrides)
    return build_container(Settings.from_env(**overrides))


def _load_urls(directory: Path) -> dict[str, str]:
    sources = Path("data/sources.yaml")
    if not sources.exists():
        return {}
    import yaml

    entries = yaml.safe_load(sources.read_text(encoding="utf-8")) or []
    return {e["name"]: e["url"] for e in entries if "name" in e and "url" in e}


def cmd_migrate(args: argparse.Namespace) -> int:
    from ragent.store.pgvector import apply_migrations

    applied = apply_migrations(Settings.from_env().database_url, Path(args.dir))
    print("applied: " + (", ".join(applied) if applied else "nothing new"))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    from ragent.ingest.loaders import load_dir
    from ragent.ingest.pipeline import ingest_documents

    c = build_container()
    directory = Path(args.directory)
    stats = ingest_documents(
        load_dir(directory, _load_urls(directory)), c.store, c.embedder, c.settings
    )
    print(
        f"ingested {stats.documents} documents ({stats.chunks} chunks), "
        f"skipped {stats.skipped} unchanged; store now holds {c.store.count()} chunks"
    )
    return 0


def cmd_chunk_stats(args: argparse.Namespace) -> int:
    from ragent.ingest.chunking import chunk_document
    from ragent.ingest.loaders import load_dir

    documents = load_dir(Path(args.directory))
    print(f"{len(documents)} documents\n")
    print("| strategy | size | chunks | mean words | min | max |")
    print("| --- | --- | --- | --- | --- | --- |")
    for strategy in ("fixed", "structure"):
        for size in args.sizes:
            overlap = min(args.overlap, size // 4)
            counts = [
                c.token_count for d in documents for c in chunk_document(d, strategy, size, overlap)
            ]
            print(
                f"| {strategy} | {size} | {len(counts)} | {sum(counts) / len(counts):.0f} "
                f"| {min(counts)} | {max(counts)} |"
            )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    c = _container(args)
    hits = c.retriever.retrieve(args.query, args.k, args.mode)
    if not hits:
        print("no results")
    for position, hit in enumerate(hits, start=1):
        ranks = ", ".join(f"{name} #{rank}" for name, rank in hit.ranks.items())
        preview = " ".join(hit.chunk.content.split())[:160]
        print(f"{position}. [{hit.chunk.id}] score={hit.score:.3f} ({ranks})")
        print(f"   {hit.chunk.section}\n   {preview}\n")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    c = _container(args)
    answerer = c.single_shot if args.single_shot else c.agent
    answer = answerer.answer(args.question)
    if args.json:
        print(json.dumps(answer.to_dict(), indent=2))
        return 0
    for step in answer.steps:
        print(f"  -> {step.tool}({json.dumps(step.arguments)}) = {step.result_ids} [{step.ms} ms]")
    print(f"\n{answer.text}\n")
    for citation in answer.citations:
        print(f"  [{citation.id}] {citation.section}")
    print(f"\n({answer.stop_reason}, {answer.latency_ms} ms, trace {answer.trace_id})")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from ragent.eval import report as render
    from ragent.eval.runner import run_answer_eval, run_retrieval_eval

    items = load_dataset(Path(args.dataset))
    if args.split:
        items = [i for i in items if i.split == args.split]
    if args.what == "validate":
        kinds = sorted({i.type for i in items})
        counts = ", ".join(f"{k}: {sum(1 for i in items if i.type == k)}" for k in kinds)
        print(f"{args.dataset}: {len(items)} questions OK ({counts})")
        return 0

    c = _container(args)
    if args.what == "retrieval":
        report = run_retrieval_eval(items, c.retriever, args.k, args.mode)
        score = report.summary[f"hit_rate@{args.k}"]
    else:
        answerer = c.single_shot if args.single_shot else c.agent
        report = run_answer_eval(items, answerer, c.store, c.chat if args.judge else None)
        score = report.summary.get("refusal_accuracy", 0.0)
    s = c.settings
    report.config.update(
        {
            "provider": s.llm_provider,
            "store": s.store,
            "chunking": f"{s.chunk_strategy}/{s.chunk_tokens}",
            "retrieval": s.retrieval_mode,
            "reranker": s.reranker,
        }
    )
    text = render.to_json(report) if args.json else render.to_markdown(report)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    if args.what == "retrieval" and args.min_hit_rate is not None and score < args.min_hit_rate:
        print(
            f"FAIL: hit rate {score:.3f} is below the floor {args.min_hit_rate:.3f}",
            file=sys.stderr,
        )
        return 1
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("ragent.api.app:create_app", factory=True, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ragent", description="Agentic RAG assistant")
    parser.add_argument("-v", "--verbose", action="store_true", help="print trace logs")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("migrate", help="apply SQL migrations")
    p.add_argument("--dir", default="db/migrations")
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("ingest", help="ingest a folder of documents")
    p.add_argument("directory")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("chunk-stats", help="compare chunking settings")
    p.add_argument("directory")
    p.add_argument("--sizes", type=int, nargs="+", default=[300, 500, 800])
    p.add_argument("--overlap", type=int, default=60)
    p.set_defaults(func=cmd_chunk_stats)

    p = sub.add_parser("search", help="run retrieval only")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--mode", choices=["hybrid", "vector", "keyword"])
    p.add_argument("--offline", metavar="DIR")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("ask", help="ask a question")
    p.add_argument("question")
    p.add_argument("--single-shot", action="store_true", help="plain RAG, no agent loop")
    p.add_argument("--json", action="store_true")
    p.add_argument("--offline", metavar="DIR")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("eval", help="run or validate the eval set")
    p.add_argument("what", choices=["validate", "retrieval", "answers"])
    p.add_argument("--dataset", default=str(DEFAULT_DATASET))
    p.add_argument("--split", choices=["dev", "test"])
    p.add_argument("-k", type=int, default=5)
    p.add_argument("--mode", choices=["hybrid", "vector", "keyword"])
    p.add_argument("--min-hit-rate", type=float, help="exit 1 if the hit rate is lower (CI gate)")
    p.add_argument("--single-shot", action="store_true")
    p.add_argument(
        "--judge", action="store_true", help="also score faithfulness with the chat model"
    )
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", help="also write the report to this file")
    p.add_argument("--offline", metavar="DIR")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("serve", help="start the HTTP API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(message)s"
    )
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - one clean line for the user, not a traceback
        if args.verbose:
            raise
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
