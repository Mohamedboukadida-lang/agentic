"""The storage interface. Two implementations: PgVectorStore and MemoryStore."""

from __future__ import annotations

from typing import Protocol

from ragent.models import Chunk, Document


class ChunkStore(Protocol):
    def upsert_document(
        self, doc: Document, content_hash: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        """Replace everything stored for doc.source."""

    def document_hash(self, source: str) -> str | None: ...

    def vector_search(self, embedding: list[float], k: int) -> list[tuple[Chunk, float]]:
        """Top k by cosine similarity, best first."""

    def keyword_search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        """Top k by keyword relevance, best first. Only chunks that match at all."""

    def get_chunk(self, source: str, ordinal: int) -> Chunk | None: ...

    def neighbours(self, source: str, ordinal: int, window: int) -> list[Chunk]:
        """The chunk and up to `window` chunks on each side, in document order."""

    def count(self) -> int: ...
