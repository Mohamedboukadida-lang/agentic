"""Metric functions. Pure functions over ids and text, so they are easy to test."""

from __future__ import annotations

import math

from ragent.eval.dataset import Expected
from ragent.models import Chunk


def is_relevant(chunk: Chunk, expected: Expected) -> bool:
    if chunk.source != expected.source:
        return False
    haystack = f"{chunk.section}\n{chunk.content}".lower()
    return all(phrase.lower() in haystack for phrase in expected.contains)


def first_relevant_rank(chunks: list[Chunk], expected: list[Expected]) -> int | None:
    """1-based rank of the first chunk relevant to any expected entry."""
    for rank, chunk in enumerate(chunks, start=1):
        if any(is_relevant(chunk, e) for e in expected):
            return rank
    return None


def recall(chunks: list[Chunk], expected: list[Expected]) -> float:
    """Share of expected entries matched by at least one chunk."""
    if not expected:
        return 0.0
    found = sum(1 for e in expected if any(is_relevant(c, e) for c in chunks))
    return found / len(expected)


def point_coverage(answer: str, points: list[str]) -> float | None:
    """Share of answer_points found in the answer (case-insensitive). None if no points."""
    if not points:
        return None
    text = " ".join(answer.lower().split())
    return sum(1 for p in points if " ".join(p.lower().split()) in text) / len(points)


def citation_precision(cited: list[Chunk], expected: list[Expected]) -> float | None:
    """Share of cited chunks that are relevant. None if nothing was cited."""
    if not cited:
        return None
    return sum(1 for c in cited if any(is_relevant(c, e) for e in expected)) / len(cited)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile, q in 0..100."""
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]
