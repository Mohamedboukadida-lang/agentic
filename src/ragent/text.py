"""Tokenisation helpers shared by keyword search, the fake embedder and the lexical reranker."""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """a an and are as at be been but by can could did do does for from had has have how i if in
    into is it its may might more most must of on or our should so such than that the their them
    then there these they this to up use used using was we were what when where which who why will
    with would you your about after all also any before between both each no not only other over
    same some under until very via per""".split()  # noqa: SIM905
)


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens. 'ReceiveMessageWaitTimeSeconds' stays one token."""
    return _TOKEN.findall(text.lower())


def normalize(token: str) -> str:
    """A deliberately tiny plural stripper. PostgreSQL does real stemming; this is only
    for the in-memory store and the lexical reranker."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def content_terms(text: str, stem: bool = True) -> list[str]:
    """Unique non-stopword tokens in first-seen order."""
    seen: dict[str, None] = {}
    for token in tokenize(text):
        if token in STOPWORDS:
            continue
        seen.setdefault(normalize(token) if stem else token, None)
    return list(seen)


def count_tokens(text: str) -> int:
    """Approximate token count: whitespace-separated words. Good enough to size chunks."""
    return len(text.split())
