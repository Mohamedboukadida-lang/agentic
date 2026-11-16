"""Checks on the user's question before anything else runs."""

from __future__ import annotations

import re

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class InputRejected(ValueError):
    """The question failed validation. The API maps this to HTTP 422."""


def validate_question(question: str, max_chars: int) -> str:
    cleaned = question.strip()
    if not cleaned:
        raise InputRejected("question is empty")
    if len(cleaned) > max_chars:
        raise InputRejected(f"question is longer than {max_chars} characters")
    if _CONTROL.search(cleaned):
        raise InputRejected("question contains control characters")
    return cleaned
