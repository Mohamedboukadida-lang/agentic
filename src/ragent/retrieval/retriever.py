"""The hybrid retriever: embed -> vector search + keyword search -> RRF -> rerank."""

from __future__ import annotations

from ragent.config import Settings
from ragent.llm.base import Embedder
from ragent.models import Chunk, ScoredChunk
from ragent.retrieval.fusion import rrf
from ragent.retrieval.rerank import Reranker
from ragent.store.base import ChunkStore

MODES = ("hybrid", "vector", "keyword")


class HybridRetriever:
    def __init__(
        self, store: ChunkStore, embedder: Embedder, reranker: Reranker, settings: Settings
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._reranker = reranker
        self._settings = settings

    def candidates(self, query: str, mode: str | None = None) -> list[ScoredChunk]:
        """First stage only: the fused candidate list before reranking."""
        s = self._settings
        mode = mode or s.retrieval_mode
        if mode not in MODES:
            raise ValueError(f"unknown retrieval mode: {mode}")
        rankings: dict[str, list[str]] = {}
        pool: dict[str, Chunk] = {}
        if mode in ("hybrid", "vector"):
            hits = self._store.vector_search(self._embedder.embed_query(query), s.candidates)
            rankings["vector"] = [chunk.id for chunk, _ in hits]
            pool.update({chunk.id: chunk for chunk, _ in hits})
        if mode in ("hybrid", "keyword"):
            hits = self._store.keyword_search(query, s.candidates)
            rankings["keyword"] = [chunk.id for chunk, _ in hits]
            pool.update({chunk.id: chunk for chunk, _ in hits})
        fused = rrf(rankings, s.rrf_k)
        ordered = sorted(fused, key=lambda chunk_id: (-fused[chunk_id], chunk_id))
        return [
            ScoredChunk(
                chunk=pool[chunk_id],
                score=fused[chunk_id],
                ranks={
                    name: ranking.index(chunk_id) + 1
                    for name, ranking in rankings.items()
                    if chunk_id in ranking
                },
            )
            for chunk_id in ordered[: s.candidates]
        ]

    def retrieve(
        self, query: str, k: int | None = None, mode: str | None = None
    ) -> list[ScoredChunk]:
        return self._reranker.rerank(query, self.candidates(query, mode), k or self._settings.top_k)
