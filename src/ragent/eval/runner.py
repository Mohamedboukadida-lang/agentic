"""Runs the eval set.

run_retrieval_eval  needs no chat model. Runs in CI.
run_answer_eval     runs the agent (or the single-shot baseline) on every question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ragent.agent.prompts import JUDGE_PROMPT
from ragent.agent.tools import format_passage
from ragent.eval import metrics
from ragent.eval.dataset import EvalItem
from ragent.guardrails.input import InputRejected
from ragent.llm.base import ChatModel
from ragent.models import Answer, Chunk
from ragent.retrieval.retriever import HybridRetriever
from ragent.store.base import ChunkStore


class Answerer(Protocol):
    def answer(self, question: str, on_step: Any = None) -> Answer: ...


@dataclass
class Report:
    kind: str  # "retrieval" | "answer"
    config: dict[str, Any]
    summary: dict[str, float]
    by_type: dict[str, dict[str, float]]
    rows: list[dict[str, Any]] = field(default_factory=list)


def _by_type(rows: list[dict[str, Any]], keys: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for kind in sorted({r["type"] for r in rows}):
        group = [r for r in rows if r["type"] == kind]
        stats: dict[str, float] = {"n": float(len(group))}
        for key in keys:
            values = [float(r[key]) for r in group if r.get(key) is not None]
            if values:
                stats[key] = round(metrics.mean(values), 4)
        out[kind] = stats
    return out


def run_retrieval_eval(
    items: list[EvalItem], retriever: HybridRetriever, k: int, mode: str | None = None
) -> Report:
    rows: list[dict[str, Any]] = []
    for item in items:
        if not item.answerable:
            continue  # nothing to retrieve for an unanswerable question
        chunks = [h.chunk for h in retriever.retrieve(item.question, k, mode)]
        rank = metrics.first_relevant_rank(chunks, item.expected)
        rows.append(
            {
                "id": item.id,
                "type": item.type,
                "hit": 1.0 if rank else 0.0,
                "rr": 1.0 / rank if rank else 0.0,
                "recall": metrics.recall(chunks, item.expected),
                "first_rank": rank,
                "retrieved": [c.id for c in chunks],
            }
        )
    summary = {
        "questions": float(len(rows)),
        f"hit_rate@{k}": round(metrics.mean([r["hit"] for r in rows]), 4),
        f"recall@{k}": round(metrics.mean([r["recall"] for r in rows]), 4),
        "mrr": round(metrics.mean([r["rr"] for r in rows]), 4),
    }
    return Report(
        "retrieval",
        {"k": k, "mode": mode or "default"},
        summary,
        _by_type(rows, ["hit", "recall", "rr"]),
        rows,
    )


def judge_faithful(judge: ChatModel, answer: str, cited: list[Chunk]) -> bool:
    prompt = JUDGE_PROMPT.format(
        passages="\n\n".join(format_passage(c) for c in cited), answer=answer
    )
    verdict = judge.chat([{"role": "user", "content": prompt}]).content.strip().upper()
    return verdict.startswith("YES")


def run_answer_eval(
    items: list[EvalItem], answerer: Answerer, store: ChunkStore, judge: ChatModel | None = None
) -> Report:
    rows: list[dict[str, Any]] = []
    for item in items:
        try:
            answer = answerer.answer(item.question)
        except InputRejected:
            rows.append(
                {"id": item.id, "type": item.type, "refusal_correct": 0.0, "error": "rejected"}
            )
            continue
        cited: list[Chunk] = []
        for citation in answer.citations:
            source, _, ordinal = citation.id.rpartition("#")
            chunk = store.get_chunk(source, int(ordinal))
            if chunk:
                cited.append(chunk)
        answered = item.answerable and not answer.refused
        row: dict[str, Any] = {
            "id": item.id,
            "type": item.type,
            "refused": answer.refused,
            "refusal_correct": 1.0 if answer.refused == (not item.answerable) else 0.0,
            "coverage": metrics.point_coverage(answer.text, item.answer_points)
            if answered
            else None,
            "citation_precision": metrics.citation_precision(cited, item.expected)
            if answered
            else None,
            "latency_s": answer.latency_ms / 1000,
            "tool_calls": len(answer.steps),
            "stop_reason": answer.stop_reason,
            "answer": answer.text,
        }
        if item.attack_marker:
            row["attack_success"] = (
                1.0 if item.attack_marker.lower() in answer.text.lower() else 0.0
            )
        if judge is not None and answered and cited:
            row["faithful"] = 1.0 if judge_faithful(judge, answer.text, cited) else 0.0
        rows.append(row)

    def avg(key: str) -> float | None:
        values = [float(r[key]) for r in rows if r.get(key) is not None]
        return round(metrics.mean(values), 4) if values else None

    latencies = [r["latency_s"] for r in rows if "latency_s" in r]
    candidates = {
        "questions": float(len(rows)),
        "refusal_accuracy": avg("refusal_correct"),
        "answer_point_coverage": avg("coverage"),
        "citation_precision": avg("citation_precision"),
        "faithfulness": avg("faithful"),
        "attack_success_rate": avg("attack_success"),
        "latency_p50_s": round(metrics.percentile(latencies, 50), 3),
        "latency_p95_s": round(metrics.percentile(latencies, 95), 3),
    }
    summary = {key: value for key, value in candidates.items() if value is not None}
    keys = ["refusal_correct", "coverage", "citation_precision", "faithful", "attack_success"]
    return Report("answer", {}, summary, _by_type(rows, keys), rows)
