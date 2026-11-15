"""Second-stage rerankers. Each takes the fused candidates and returns the best top_k.

Score scales (this matters for Settings.min_relevance):
    none      the fused RRF score, at most 2 / (rrf_k + 1), about 0.033 with the default
    lexical   0..1  = 0.6 * share of query terms in the passage + 0.4 * normalised RRF
    llm       0..1  = the model's 0-10 relevance score divided by 10
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from ragent.llm.base import ChatModel
from ragent.models import ScoredChunk
from ragent.text import content_terms, normalize, tokenize


class Reranker(Protocol):
    def rerank(
        self, query: str, candidates: list[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]: ...


class NoReranker:
    def rerank(self, query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
        return candidates[:top_k]


class LexicalReranker:
    """Free and deterministic. Rewards passages that contain the question's content words."""

    def __init__(self, overlap_weight: float = 0.6) -> None:
        self._w = overlap_weight

    def rerank(self, query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
        if not candidates:
            return []
        terms = content_terms(query)
        best = max(c.score for c in candidates) or 1.0
        rescored: list[tuple[float, int, ScoredChunk]] = []
        for position, candidate in enumerate(candidates):
            words = {
                normalize(t)
                for t in tokenize(f"{candidate.chunk.section} {candidate.chunk.content}")
            }
            overlap = sum(1 for t in terms if t in words) / len(terms) if terms else 0.0
            score = self._w * overlap + (1 - self._w) * (candidate.score / best)
            rescored.append((score, position, candidate))
        rescored.sort(key=lambda item: (-item[0], item[1]))
        return [ScoredChunk(c.chunk, score, c.ranks) for score, _, c in rescored[:top_k]]


_PROMPT = """You rate how well each passage answers a question.
Return only a JSON array with one object per passage, like
[{{"i": 1, "score": 7}}, {{"i": 2, "score": 0}}]
where score is an integer from 0 (irrelevant) to 10 (answers the question directly).

Question: {query}

Passages:
{passages}"""


class LLMReranker:
    """One listwise model call per query. If the model's output cannot be parsed, the
    original order is kept, so a bad model can never make retrieval crash."""

    def __init__(self, chat: ChatModel, passage_chars: int = 600) -> None:
        self._chat = chat
        self._chars = passage_chars

    def rerank(self, query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
        if not candidates:
            return []
        listing = "\n\n".join(
            f"[{i}] {c.chunk.section}\n{c.chunk.content[: self._chars]}"
            for i, c in enumerate(candidates, start=1)
        )
        prompt = _PROMPT.format(query=query, passages=listing)
        response = self._chat.chat([{"role": "user", "content": prompt}])
        scores = parse_scores(response.content, len(candidates))
        if scores is None:
            return candidates[:top_k]
        order = sorted(range(len(candidates)), key=lambda i: (-scores.get(i + 1, 0.0), i))
        return [
            ScoredChunk(candidates[i].chunk, scores.get(i + 1, 0.0) / 10.0, candidates[i].ranks)
            for i in order[:top_k]
        ]


def parse_scores(text: str, n: int) -> dict[int, float] | None:
    """Pull [{"i": int, "score": number}, ...] out of model output. None if unusable."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return None
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    scores: dict[int, float] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        index, score = item.get("i"), item.get("score")
        if (
            isinstance(index, int)
            and not isinstance(score, bool)
            and isinstance(score, int | float)
            and 1 <= index <= n
        ):
            scores[index] = max(0.0, min(10.0, float(score)))
    return scores or None
