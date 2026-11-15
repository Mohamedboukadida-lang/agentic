"""In-memory store: exact cosine search and BM25. No database needed.

Used by unit tests, CI and the offline demo. It scans every chunk on each query, which is
fine for a few thousand chunks and wrong for anything larger.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from ragent.models import Chunk, Document
from ragent.text import content_terms, normalize, tokenize

_K1 = 1.5
_B = 0.75


@dataclass
class _Entry:
    title: str
    content_hash: str
    chunks: list[Chunk]
    embeddings: list[list[float]]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class MemoryStore:
    def __init__(self) -> None:
        self._docs: dict[str, _Entry] = {}
        self._bm25: tuple[list[Chunk], list[Counter[str]], Counter[str], float] | None = None

    def upsert_document(
        self, doc: Document, content_hash: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings differ in length")
        self._docs[doc.source] = _Entry(doc.title, content_hash, list(chunks), list(embeddings))
        self._bm25 = None

    def document_hash(self, source: str) -> str | None:
        entry = self._docs.get(source)
        return entry.content_hash if entry else None

    def count(self) -> int:
        return sum(len(e.chunks) for e in self._docs.values())

    def vector_search(self, embedding: list[float], k: int) -> list[tuple[Chunk, float]]:
        scored = [
            (chunk, _cosine(embedding, vector))
            for entry in self._docs.values()
            for chunk, vector in zip(entry.chunks, entry.embeddings, strict=True)
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return scored[:k]

    def _index(self) -> tuple[list[Chunk], list[Counter[str]], Counter[str], float]:
        if self._bm25 is None:
            chunks = [c for e in self._docs.values() for c in e.chunks]
            frequencies = [
                Counter(normalize(t) for t in tokenize(f"{c.section} {c.content}")) for c in chunks
            ]
            document_frequency: Counter[str] = Counter()
            for tf in frequencies:
                document_frequency.update(tf.keys())
            total = sum(sum(tf.values()) for tf in frequencies)
            average_length = total / len(chunks) if chunks else 0.0
            self._bm25 = (chunks, frequencies, document_frequency, average_length)
        return self._bm25

    def keyword_search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        chunks, frequencies, document_frequency, average_length = self._index()
        terms = content_terms(query)
        n = len(chunks)
        scored: list[tuple[Chunk, float]] = []
        for chunk, tf in zip(chunks, frequencies, strict=True):
            length = sum(tf.values())
            score = 0.0
            for term in terms:
                f = tf.get(term, 0)
                if not f:
                    continue
                df = document_frequency[term]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                score += idf * f * (_K1 + 1) / (f + _K1 * (1 - _B + _B * length / average_length))
            if score > 0:
                scored.append((chunk, score))
        scored.sort(key=lambda pair: (-pair[1], pair[0].id))
        return scored[:k]

    def get_chunk(self, source: str, ordinal: int) -> Chunk | None:
        entry = self._docs.get(source)
        if entry and 0 <= ordinal < len(entry.chunks):
            return entry.chunks[ordinal]
        return None

    def neighbours(self, source: str, ordinal: int, window: int) -> list[Chunk]:
        entry = self._docs.get(source)
        if not entry or not 0 <= ordinal < len(entry.chunks):
            return []
        return entry.chunks[max(0, ordinal - window) : ordinal + window + 1]
