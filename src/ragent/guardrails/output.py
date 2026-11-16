"""Checks on the model's final answer.

An answer may only cite chunks that were retrieved in this run, may only contain links
that appear in those chunks, and has a length cap.
"""

from __future__ import annotations

import re

from ragent.models import REFUSAL, Chunk

CITATION = re.compile(r"\[([A-Za-z0-9_./-]+#\d+)\]")
_URL = re.compile(r"https?://[^\s)\]>\"']+")
_SPACES = re.compile(r"[ \t]{2,}")


def is_refusal(text: str) -> bool:
    return text.strip().lower().replace("’", "'").startswith(REFUSAL[:30].lower())


def validate_answer(text: str, seen: dict[str, Chunk], max_chars: int) -> tuple[str, list[str]]:
    """Return (cleaned_text, valid_citation_ids in first-use order)."""
    valid: dict[str, None] = {}

    def keep_known(match: re.Match[str]) -> str:
        if match.group(1) in seen:
            valid.setdefault(match.group(1), None)
            return match.group(0)
        return ""

    cleaned = CITATION.sub(keep_known, text)
    corpus = "\n".join(chunk.content for chunk in seen.values())
    cleaned = _URL.sub(lambda m: m.group(0) if m.group(0) in corpus else "", cleaned)
    cleaned = _SPACES.sub(" ", cleaned).replace(" .", ".").replace(" ,", ",").strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip() + " [truncated]"
    return cleaned, list(valid)
