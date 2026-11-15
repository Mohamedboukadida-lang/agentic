"""Plain data types passed between modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

REFUSAL = "I don't have enough context in the indexed documents to answer that."


@dataclass(frozen=True)
class Document:
    source: str  # short stable id, e.g. "sqs"
    title: str
    text: str  # cleaned text in Markdown-like form (headings start with '#')
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    source: str
    ordinal: int
    section: str  # heading path, e.g. "Amazon SQS > Visibility timeout"
    content: str
    token_count: int

    @property
    def id(self) -> str:
        """Citation id. Stable while the document and the chunking settings stay the same."""
        return f"{self.source}#{self.ordinal}"


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    # 1-based rank in each first-stage list, e.g. {"vector": 3, "keyword": 1}
    ranks: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass
class Step:
    tool: str
    arguments: dict[str, Any]
    result_ids: list[str]
    ms: int
    note: str = ""


@dataclass(frozen=True)
class Citation:
    id: str
    source: str
    section: str


@dataclass
class Answer:
    text: str
    refused: bool
    citations: list[Citation]
    steps: list[Step]
    trace_id: str
    latency_ms: int
    dropped_passages: int = 0  # passages removed by the injection scanner
    stop_reason: str = "answered"  # answered | refused | max_steps | no_citations

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.text,
            "refused": self.refused,
            "citations": [c.__dict__ for c in self.citations],
            "steps": [s.__dict__ for s in self.steps],
            "trace_id": self.trace_id,
            "latency_ms": self.latency_ms,
            "dropped_passages": self.dropped_passages,
            "stop_reason": self.stop_reason,
        }
