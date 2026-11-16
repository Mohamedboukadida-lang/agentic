"""The agent's three tools and the code that runs them.

Every tool returns passages wrapped in <passage> tags. Passages that trip the injection
scanner are dropped here, before the model can read them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ragent.config import Settings
from ragent.guardrails.injection import scan
from ragent.models import Chunk
from ragent.retrieval.retriever import HybridRetriever
from ragent.store.base import ChunkStore


def _function(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _function(
        "search_docs",
        "Search the indexed AWS documentation. Returns the most relevant passages with their ids.",
        {
            "query": {"type": "string", "description": "What to look for, in plain words."},
            "k": {
                "type": "integer",
                "description": "How many passages to return (1-10). Default 5.",
            },
        },
        ["query"],
    ),
    _function(
        "get_section",
        "Read the passages around a known passage, in document order. Use when one is cut off.",
        {
            "chunk_id": {"type": "string", "description": "A passage id such as sqs#4."},
            "window": {
                "type": "integer",
                "description": "Passages to include on each side (1-3). Default 1.",
            },
        },
        ["chunk_id"],
    ),
    _function(
        "compare_services",
        "Retrieve passages about the same aspect for two services, side by side.",
        {
            "service_a": {"type": "string", "description": "First service, e.g. SQS."},
            "service_b": {"type": "string", "description": "Second service, e.g. EventBridge."},
            "aspect": {
                "type": "string",
                "description": "What to compare, e.g. ordering guarantees.",
            },
        },
        ["service_a", "service_b", "aspect"],
    ),
]
TOOL_NAMES = frozenset(schema["function"]["name"] for schema in TOOL_SCHEMAS)


@dataclass
class ToolResult:
    text: str
    chunks: list[Chunk] = field(default_factory=list)
    dropped: int = 0  # passages removed by the injection scanner
    error: bool = False


def format_passage(chunk: Chunk) -> str:
    # Neutralise a closing tag inside the content so a document cannot break out of its wrapper.
    body = chunk.content.replace("</passage", "&lt;/passage")
    # '>' would end the tag early for a naive parser, so the heading path uses '/'.
    section = chunk.section.replace('"', "'").replace(">", "/")
    return (
        f'<passage id="{chunk.id}" source="{chunk.source}" section="{section}">\n{body}\n</passage>'
    )


def _as_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


class Toolbox:
    def __init__(self, retriever: HybridRetriever, store: ChunkStore, settings: Settings) -> None:
        self._retriever = retriever
        self._store = store
        self._settings = settings

    def run(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        try:
            if name == "search_docs":
                return self._search(str(arguments["query"]), _as_int(arguments.get("k"), 5, 1, 10))
            if name == "get_section":
                return self._section(
                    str(arguments["chunk_id"]), _as_int(arguments.get("window"), 1, 1, 3)
                )
            if name == "compare_services":
                return self._compare(
                    str(arguments["service_a"]),
                    str(arguments["service_b"]),
                    str(arguments["aspect"]),
                )
        except KeyError as missing:
            return ToolResult(f"Error: missing argument {missing} for {name}.", error=True)
        return ToolResult(
            f"Error: unknown tool {name}. Available: {sorted(TOOL_NAMES)}.", error=True
        )

    def _screen(self, chunks: list[Chunk]) -> tuple[list[Chunk], int]:
        if not self._settings.injection_scan:
            return chunks, 0
        clean = [c for c in chunks if not scan(c.content)]
        return clean, len(chunks) - len(clean)

    def _retrieve(self, query: str, k: int) -> tuple[list[Chunk], int]:
        hits = self._retriever.retrieve(query, k)
        relevant = [h.chunk for h in hits if h.score >= self._settings.min_relevance]
        return self._screen(relevant)

    def _search(self, query: str, k: int) -> ToolResult:
        chunks, dropped = self._retrieve(query, k)
        if not chunks:
            return ToolResult("No relevant passages found.", dropped=dropped)
        return ToolResult("\n\n".join(format_passage(c) for c in chunks), chunks, dropped)

    def _section(self, chunk_id: str, window: int) -> ToolResult:
        source, _, ordinal = chunk_id.strip("[] ").rpartition("#")
        if not source or not ordinal.isdigit():
            return ToolResult(f"Error: {chunk_id!r} is not a passage id like sqs#4.", error=True)
        chunks, dropped = self._screen(self._store.neighbours(source, int(ordinal), window))
        if not chunks:
            return ToolResult(f"No passage with id {chunk_id}.", dropped=dropped)
        return ToolResult("\n\n".join(format_passage(c) for c in chunks), chunks, dropped)

    def _compare(self, service_a: str, service_b: str, aspect: str) -> ToolResult:
        parts: list[str] = []
        found: list[Chunk] = []
        dropped = 0
        for service in (service_a, service_b):
            chunks, removed = self._retrieve(f"{service} {aspect}", 3)
            dropped += removed
            found.extend(chunks)
            body = "\n\n".join(format_passage(c) for c in chunks) or "No relevant passages found."
            parts.append(f"## {service}: {aspect}\n{body}")
        unique = list({c.id: c for c in found}.values())
        return ToolResult("\n\n".join(parts), unique, dropped)
