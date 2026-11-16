"""Command line interface.  Run `ragent --help`.

    ragent migrate                         apply db/migrations to PostgreSQL
    ragent ingest data/sample              load, chunk, embed and store a folder
    ragent chunk-stats data/sample         compare chunking settings without storing
    ragent search "visibility timeout"     show retrieval with per-stage ranks
    ragent ask "..."                       ask the agent (--single-shot for plain RAG)

Add --offline DIR to search and ask to run with fake providers and an in-memory store
filled from DIR. No Ollama and no database needed.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ragent.config import Settings
from ragent.factory import Container, build_container, build_offline_container


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
