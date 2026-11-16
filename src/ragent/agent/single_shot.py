"""Plain RAG without an agent: retrieve once, answer once.

This is the baseline the agent has to beat. Day 8 compares the two on comparison and
multi-step questions.
"""

from __future__ import annotations

from ragent.agent.prompts import SINGLE_SHOT_PROMPT
from ragent.agent.tools import format_passage
from ragent.config import Settings
from ragent.guardrails.injection import scan
from ragent.guardrails.input import validate_question
from ragent.guardrails.output import is_refusal, validate_answer
from ragent.llm.base import ChatModel
from ragent.models import REFUSAL, Answer, Citation, Step
from ragent.observability.tracing import Tracer
from ragent.retrieval.retriever import HybridRetriever


class SingleShotRAG:
    def __init__(self, chat: ChatModel, retriever: HybridRetriever, settings: Settings) -> None:
        self._chat = chat
        self._retriever = retriever
        self._settings = settings

    def answer(self, question: str, on_step: object = None) -> Answer:
        s = self._settings
        tracer = Tracer()
        question = validate_question(question, s.max_question_chars)
        with tracer.span("retrieve"):
            hits = [h for h in self._retriever.retrieve(question) if h.score >= s.min_relevance]
        chunks = [h.chunk for h in hits]
        dropped = 0
        if s.injection_scan:
            clean = [c for c in chunks if not scan(c.content)]
            dropped, chunks = len(chunks) - len(clean), clean
        seen = {c.id: c for c in chunks}
        step = Step("retrieve", {"query": question}, list(seen), tracer.elapsed_ms())

        def result(text: str, citations: list[Citation], reason: str) -> Answer:
            return Answer(
                text,
                reason != "answered",
                citations,
                [step],
                tracer.trace_id,
                tracer.elapsed_ms(),
                dropped,
                reason,
            )

        if not chunks:
            return result(REFUSAL, [], "refused")
        prompt = SINGLE_SHOT_PROMPT.format(
            passages="\n\n".join(format_passage(c) for c in chunks), question=question
        )
        with tracer.span("chat"):
            response = self._chat.chat([{"role": "user", "content": prompt}])
        if is_refusal(response.content):
            return result(REFUSAL, [], "refused")
        cleaned, valid_ids = validate_answer(response.content, seen, s.max_answer_chars)
        if not valid_ids:
            return result(REFUSAL, [], "no_citations")
        citations = [Citation(i, seen[i].source, seen[i].section) for i in valid_ids]
        return result(cleaned, citations, "answered")
