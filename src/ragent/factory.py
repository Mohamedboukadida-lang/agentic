"""Wires the parts together from Settings. Every entry point builds its objects here,
so they always run the same code."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ragent.config import Settings
from ragent.ingest.loaders import load_dir
from ragent.ingest.pipeline import ingest_documents
from ragent.llm.base import ChatModel, Embedder
from ragent.retrieval.rerank import LexicalReranker, LLMReranker, NoReranker, Reranker
from ragent.retrieval.retriever import HybridRetriever
from ragent.store.base import ChunkStore


@dataclass
class Container:
    settings: Settings
    store: ChunkStore
    embedder: Embedder
    chat: ChatModel
    retriever: HybridRetriever


def build_embedder(s: Settings) -> Embedder:
    if s.llm_provider == "fake":
        from ragent.llm.fake import FakeEmbedder

        return FakeEmbedder(s.embed_dim)
    from ragent.llm.ollama import OllamaEmbedder

    return OllamaEmbedder(
        s.ollama_url,
        s.embed_model,
        s.embed_dim,
        s.embed_query_prefix,
        s.embed_doc_prefix,
        s.request_timeout_s,
    )


def build_chat(s: Settings) -> ChatModel:
    if s.llm_provider == "fake":
        from ragent.llm.fake import ExtractiveChat

        return ExtractiveChat()
    from ragent.llm.ollama import OllamaChat

    return OllamaChat(s.ollama_url, s.chat_model, s.request_timeout_s)


def build_store(s: Settings) -> ChunkStore:
    if s.store == "memory":
        from ragent.store.memory import MemoryStore

        return MemoryStore()
    from ragent.store.pgvector import PgVectorStore

    return PgVectorStore(s.database_url)


def build_reranker(s: Settings, chat: ChatModel) -> Reranker:
    if s.reranker == "none":
        return NoReranker()
    if s.reranker == "llm":
        return LLMReranker(chat)
    return LexicalReranker()


def build_container(
    settings: Settings | None = None,
    *,
    store: ChunkStore | None = None,
    embedder: Embedder | None = None,
    chat: ChatModel | None = None,
) -> Container:
    """Pass store, embedder or chat to override what the settings would build (tests do)."""
    s = settings or Settings.from_env()
    store = store or build_store(s)
    embedder = embedder or build_embedder(s)
    chat = chat or build_chat(s)
    retriever = HybridRetriever(store, embedder, build_reranker(s, chat), s)
    return Container(
        settings=s,
        store=store,
        embedder=embedder,
        chat=chat,
        retriever=retriever,
    )


def build_offline_container(corpus: Path, **overrides: object) -> Container:
    """No Ollama, no database: fake providers and an in-memory store filled from `corpus`.
    Used by `--offline`, the unit tests and CI."""
    base = Settings.from_env().model_dump()
    base.update({"llm_provider": "fake", "store": "memory", "embed_dim": 256})
    base.update(overrides)
    container = build_container(Settings(**base))
    ingest_documents(load_dir(corpus), container.store, container.embedder, container.settings)
    return container
