"""Ollama providers. Talks to the local Ollama HTTP API (default http://localhost:11434).

Endpoints used:
    POST /api/embed  {"model", "input": [str, ...]}        -> {"embeddings": [[float, ...], ...]}
    POST /api/chat   {"model", "messages", "tools", ...}   -> {"message": {"content", "tool_calls"}}
"""

from __future__ import annotations

from typing import Any

from ragent.llm.base import Message
from ragent.models import ChatResponse, ToolCall


class OllamaError(RuntimeError):
    """Ollama is unreachable or returned an error."""


def _post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    import httpx  # imported lazily so the package works offline without httpx

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise OllamaError(f"Ollama request to {url} failed: {exc}") from exc


class OllamaEmbedder:
    def __init__(
        self,
        url: str,
        model: str,
        dim: int,
        query_prefix: str = "",
        doc_prefix: str = "",
        timeout: float = 180.0,
        batch_size: int = 32,
    ) -> None:
        self._url = url.rstrip("/") + "/api/embed"
        self._model = model
        self.dim = dim
        self._query_prefix = query_prefix
        self._doc_prefix = doc_prefix
        self._timeout = timeout
        self._batch_size = batch_size

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(inputs), self._batch_size):
            batch = inputs[start : start + self._batch_size]
            data = _post(self._url, {"model": self._model, "input": batch}, self._timeout)
            vectors = data.get("embeddings") or []
            if len(vectors) != len(batch):
                raise OllamaError(f"expected {len(batch)} embeddings, got {len(vectors)}")
            for vector in vectors:
                if len(vector) != self.dim:
                    raise OllamaError(
                        f"model {self._model} returned {len(vector)} dimensions, "
                        f"but RAGENT_EMBED_DIM is {self.dim}"
                    )
            out.extend(vectors)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([self._doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self._query_prefix + text])[0]


class OllamaChat:
    def __init__(self, url: str, model: str, timeout: float = 180.0) -> None:
        self._url = url.rstrip("/") + "/api/chat"
        self._model = model
        self._timeout = timeout

    def chat(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0},
        }
        if tools:
            payload["tools"] = tools
        data = _post(self._url, payload, self._timeout)
        message = data.get("message") or {}
        calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments = function.get("arguments") or {}
            if isinstance(function.get("name"), str) and isinstance(arguments, dict):
                calls.append(ToolCall(name=function["name"], arguments=arguments))
        return ChatResponse(content=message.get("content") or "", tool_calls=calls)
