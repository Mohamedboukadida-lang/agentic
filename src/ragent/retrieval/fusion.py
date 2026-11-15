"""Reciprocal rank fusion (Cormack, Clarke and Buettcher, 2009).

Each list votes for an item with 1 / (k + rank). Only ranks matter, so lists whose scores
live on different scales (cosine similarity, BM25) can be merged without normalising.
"""

from __future__ import annotations


def rrf(rankings: dict[str, list[str]], k: int = 60) -> dict[str, float]:
    """`rankings` maps a list name to item ids, best first. Returns id -> fused score."""
    fused: dict[str, float] = {}
    for ranking in rankings.values():
        for position, item in enumerate(ranking, start=1):
            fused[item] = fused.get(item, 0.0) + 1.0 / (k + position)
    return fused
