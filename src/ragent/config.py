"""All settings in one typed object.

Nothing else in the package reads environment variables. Every field can be set with
RAGENT_<FIELD_NAME_IN_CAPS>, for example RAGENT_TOP_K=8.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field, model_validator


class Settings(BaseModel):
    # --- providers ---
    llm_provider: str = Field("ollama", pattern="^(ollama|fake)$")
    ollama_url: str = "http://localhost:11434"
    chat_model: str = "llama3.1:8b"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = Field(768, gt=0)
    # nomic-embed-text expects these task prefixes; other models may need none.
    embed_query_prefix: str = "search_query: "
    embed_doc_prefix: str = "search_document: "
    request_timeout_s: float = Field(180.0, gt=0)

    # --- store ---
    store: str = Field("pgvector", pattern="^(pgvector|memory)$")
    database_url: str = "postgresql://ragent:ragent@localhost:5432/ragent"

    # --- chunking (sizes are in whitespace-separated words, an approximation of tokens) ---
    chunk_strategy: str = Field("structure", pattern="^(structure|fixed)$")
    chunk_tokens: int = Field(500, gt=0)
    chunk_overlap: int = Field(60, ge=0)

    # --- retrieval ---
    retrieval_mode: str = Field("hybrid", pattern="^(hybrid|vector|keyword)$")
    candidates: int = Field(20, gt=0)
    top_k: int = Field(5, gt=0)
    rrf_k: int = Field(60, gt=0)
    reranker: str = Field("lexical", pattern="^(none|lexical|llm)$")

    # --- agent ---
    max_steps: int = Field(6, gt=0)
    max_tool_calls: int = Field(8, gt=0)
    tool_output_chars: int = Field(6000, gt=0)
    # Passages scoring below this are not shown to the model. The scale depends on the
    # reranker (see retrieval/rerank.py), so tune it per reranker. 0 disables the floor.
    min_relevance: float = Field(0.0, ge=0)

    # --- guardrails ---
    max_question_chars: int = Field(2000, gt=0)
    max_answer_chars: int = Field(4000, gt=0)
    injection_scan: bool = True

    @model_validator(mode="after")
    def _check(self) -> Settings:
        if self.chunk_overlap >= self.chunk_tokens:
            raise ValueError("chunk_overlap must be smaller than chunk_tokens")
        if self.top_k > self.candidates:
            raise ValueError("top_k cannot exceed candidates")
        return self

    @classmethod
    def from_env(cls, **overrides: Any) -> Settings:
        """Build settings from RAGENT_* environment variables, then apply overrides."""
        data: dict[str, Any] = {}
        for name in cls.model_fields:
            value = os.environ.get(f"RAGENT_{name.upper()}")
            if value is not None:
                data[name] = value
        data.update(overrides)
        return cls(**data)
