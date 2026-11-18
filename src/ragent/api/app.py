"""FastAPI app. A thin layer: all logic lives in the package.

Run with:  uvicorn ragent.api.app:create_app --factory --port 8000
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ragent.factory import Container, build_container


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    k: int = Field(5, ge=1, le=20)


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

    return app
