"""FastAPI app. A thin layer: all logic lives in the package.

Run with:  uvicorn ragent.api.app:create_app --factory --port 8000
"""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ragent.factory import Container, build_container
from ragent.guardrails.input import InputRejected
from ragent.models import Step


class AskRequest(BaseModel):
    question: str


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(5, ge=1, le=20)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_app(container: Container | None = None) -> FastAPI:
    """Pass a container in tests. In production it is built from the environment on
    first use, so the app can start before Ollama or the database is up."""
    app = FastAPI(title="ragent", version="0.1.0")
    state: dict[str, Container] = {}
    if container is not None:
        state["c"] = container

    def get() -> Container:
        if "c" not in state:
            state["c"] = build_container()
        return state["c"]

    def unavailable(exc: Exception) -> HTTPException:
        return HTTPException(
            status_code=503, detail=f"backend unavailable: {type(exc).__name__}: {exc}"
        )

    @app.get("/health")
    def health() -> dict[str, Any]:
        try:
            c = get()
            chunks = c.store.count()
        except Exception as exc:  # noqa: BLE001 - report any backend failure as 503
            raise unavailable(exc) from exc
        s = c.settings
        return {
            "status": "ok",
            "store": s.store,
            "provider": s.llm_provider,
            "chat_model": s.chat_model,
            "embed_model": s.embed_model,
            "chunks": chunks,
        }

    @app.post("/search")
    def search(request: SearchRequest) -> dict[str, Any]:
        try:
            hits = get().retriever.retrieve(request.query, request.k)
        except Exception as exc:  # noqa: BLE001
            raise unavailable(exc) from exc
        return {
            "results": [
                {
                    "id": h.chunk.id,
                    "source": h.chunk.source,
                    "section": h.chunk.section,
                    "content": h.chunk.content,
                    "score": round(h.score, 4),
                    "ranks": h.ranks,
                }
                for h in hits
            ]
        }

    @app.post("/ask")
    def ask(request: AskRequest) -> dict[str, Any]:
        try:
            return get().agent.answer(request.question).to_dict()
        except InputRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise unavailable(exc) from exc

    @app.post("/ask/stream")
    def ask_stream(request: AskRequest) -> StreamingResponse:
        """Server-sent events: `step` per tool call, then `answer`, then `done`.
        The agent runs in a worker thread and pushes events onto a queue."""
        events: queue.Queue[str | None] = queue.Queue()

        def on_step(step: Step) -> None:
            events.put(_sse("step", step.__dict__))

        def work() -> None:
            try:
                answer = get().agent.answer(request.question, on_step=on_step)
                events.put(_sse("answer", answer.to_dict()))
            except InputRejected as exc:
                events.put(_sse("error", {"status": 422, "detail": str(exc)}))
            except Exception as exc:  # noqa: BLE001
                events.put(_sse("error", {"status": 503, "detail": f"{type(exc).__name__}: {exc}"}))
            finally:
                events.put(_sse("done", {}))
                events.put(None)

        threading.Thread(target=work, daemon=True).start()

        def stream() -> Iterator[str]:
            while (event := events.get()) is not None:
                yield event

        return StreamingResponse(stream(), media_type="text/event-stream")

    return app
