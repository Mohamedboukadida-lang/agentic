"""Load -> chunk -> embed -> store. Safe to re-run: unchanged documents are skipped."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ragent.config import Settings
from ragent.ingest.chunking import chunk_document
from ragent.llm.base import Embedder
from ragent.models import Chunk, Document
from ragent.store.base import ChunkStore


@dataclass
class IngestStats:
    documents: int = 0
    skipped: int = 0
    chunks: int = 0


def content_hash(doc: Document, settings: Settings) -> str:
    """Hash of everything that decides the stored rows. Changing the text, the chunking
    settings or the embedding model changes the hash and forces a re-ingest."""
    recipe = (
        f"{settings.chunk_strategy}:{settings.chunk_tokens}:{settings.chunk_overlap}:"
        f"{settings.embed_model}:{settings.embed_dim}"
    )
    return hashlib.sha256(f"{recipe}\n{doc.title}\n{doc.text}".encode()).hexdigest()


def embedding_text(doc: Document, chunk: Chunk) -> str:
    """What gets embedded. The title and heading path give a short chunk its context."""
    header = " | ".join(part for part in (doc.title, chunk.section) if part)
    return f"{header}\n{chunk.content}" if header else chunk.content


def ingest_documents(
    documents: list[Document], store: ChunkStore, embedder: Embedder, settings: Settings
) -> IngestStats:
    stats = IngestStats()
    for doc in documents:
        digest = content_hash(doc, settings)
        if store.document_hash(doc.source) == digest:
            stats.skipped += 1
            continue
        chunks = chunk_document(
            doc, settings.chunk_strategy, settings.chunk_tokens, settings.chunk_overlap
        )
        if not chunks:
            stats.skipped += 1
            continue
        embeddings = embedder.embed_documents([embedding_text(doc, c) for c in chunks])
        store.upsert_document(doc, digest, chunks, embeddings)
        stats.documents += 1
        stats.chunks += len(chunks)
    return stats
