"""Deterministic offline providers for tests, CI and a no-model demo.

They are not models. FakeEmbedder is a hashed bag of words, so it only captures word
overlap. ExtractiveChat follows a fixed script: search once, then quote the best passage.
Use them to test plumbing, never to judge answer quality.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

from ragent.llm.base import Message
from ragent.models import REFUSAL, ChatResponse, ToolCall
from ragent.text import content_terms


class FakeEmbedder:
    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for term in content_terms(text):
            digest = int(hashlib.sha1(term.encode()).hexdigest()[:8], 16)
            sign = 1.0 if (digest >> 31) & 1 else -1.0
            vector[digest % self.dim] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class ScriptedChat:
    """Returns the given responses in order and records every call. For unit tests."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse:
        self.calls.append([dict(m) for m in messages])
        if not self._responses:
            raise AssertionError("ScriptedChat ran out of responses")
        return self._responses.pop(0)


_PASSAGE = re.compile(r'<passage id="([^"]+)"[^>]*>\n(.*?)\n</passage>', re.DOTALL)


class ExtractiveChat:
    """A stand-in 'model': calls search_docs with the question, then answers with the
    first sentence of the top passage and cites it. Refuses when nothing came back."""

    def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse:
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        if tools and not tool_messages:
            question = next(m["content"] for m in reversed(messages) if m.get("role") == "user")
            return ChatResponse("", [ToolCall("search_docs", {"query": question})])
        # Passages arrive in tool messages (agent) or inside the user prompt (single-shot).
        for message in tool_messages or [m for m in messages if m.get("role") == "user"]:
            match = _PASSAGE.search(message.get("content", ""))
            if match:
                passage_id, body = match.group(1), " ".join(match.group(2).split())
                sentence = re.split(r"(?<=[.!?])\s", body, maxsplit=1)[0]
                return ChatResponse(f"{sentence} [{passage_id}]")
        return ChatResponse(REFUSAL)
