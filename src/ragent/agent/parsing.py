"""Recover tool calls that a model wrote as plain text.

Small local models sometimes answer with
    {"name": "search_docs", "arguments": {"query": "..."}}
in the message content and leave the tool_calls field empty. This parser accepts that
form (also with "parameters" as the key, inside a code fence, or as a list).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from ragent.models import ToolCall

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


def _to_call(item: Any, known: Iterable[str]) -> ToolCall | None:
    if not isinstance(item, dict):
        return None
    if isinstance(item.get("function"), dict):
        item = item["function"]
    name = item.get("name")
    arguments = item.get("arguments", item.get("parameters"))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return None
    if isinstance(name, str) and name in known and isinstance(arguments, dict):
        return ToolCall(name, arguments)
    return None


def parse_text_tool_calls(content: str, known: Iterable[str]) -> list[ToolCall]:
    text = _FENCE.sub("", content.strip())
    if not text or text[0] not in "{[":
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    known = set(known)
    items = data if isinstance(data, list) else [data]
    calls = [_to_call(item, known) for item in items]
    return [c for c in calls if c is not None] if all(calls) else []
