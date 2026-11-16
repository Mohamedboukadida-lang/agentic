"""Pattern scanner for instructions hidden in retrieved text (indirect prompt injection).

A passage that matches is dropped before the model sees it.

Known limits, state them in your README:
  * It only catches phrasings listed here. A paraphrase or another language gets through.
  * It can drop honest text, e.g. documentation that quotes such a phrase as an example.
The structural defence (passages wrapped in tags and declared to be data in the system
prompt) is always on and does not depend on this scanner.
"""

from __future__ import annotations

import re

_FLAGS = re.IGNORECASE
PATTERNS: dict[str, re.Pattern[str]] = {
    "override": re.compile(
        r"\b(ignore|disregard|forget)\b[^.\n]{0,40}\b(previous|prior|above|earlier|preceding)\b"
        r"[^.\n]{0,20}\b(instruction|prompt|message|rule|direction)s?\b",
        _FLAGS,
    ),
    "new_instructions": re.compile(r"\bnew (system )?instructions?\s*:", _FLAGS),
    "role_change": re.compile(
        r"\byou are now\b|\bact as (an?|the) (system|admin|developer)\b", _FLAGS
    ),
    "prompt_leak": re.compile(
        r"\b(reveal|print|show|repeat|output)\b[^.\n]{0,30}\b(system|hidden|initial) prompt\b",
        _FLAGS,
    ),
    "role_tag": re.compile(
        r"<\s*/?\s*(system|assistant|tool|passage)\b|^\s*(system|assistant)\s*:",
        _FLAGS | re.MULTILINE,
    ),
    "forced_reply": re.compile(r"\b(reply|respond|answer) (only )?with\b[^.\n]{0,40}['\"]", _FLAGS),
    "hide_from_user": re.compile(r"\bdo not (tell|inform|mention to) the user\b", _FLAGS),
}


def scan(text: str) -> list[str]:
    """Names of the patterns that match. Empty list means the text looks clean."""
    return [name for name, pattern in PATTERNS.items() if pattern.search(text)]
