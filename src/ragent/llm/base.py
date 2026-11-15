"""Provider interfaces. Anything that implements these can be plugged in.

Messages use the common chat format:
    {"role": "system" | "user" | "assistant" | "tool", "content": str, ...}
An assistant message that calls tools carries
    "tool_calls": [{"function": {"name": str, "arguments": dict}}]
and each tool result is a message with role "tool" and "tool_name".
"""

from __future__ import annotations

from typing import Any, Protocol

from ragent.models import ChatResponse

Message = dict[str, Any]


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse: ...
