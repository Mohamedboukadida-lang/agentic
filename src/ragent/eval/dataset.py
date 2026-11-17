"""The eval dataset: one JSON object per line.

    {"id": "sqs-003", "type": "identifier", "answerable": true,
     "question": "What is the default visibility timeout for an SQS queue?",
     "expected": [{"source": "sqs", "contains": ["visibility timeout", "30 seconds"]}],
     "answer_points": ["30 seconds"]}

A retrieved chunk is relevant to an `expected` entry when it comes from that source and
contains every phrase in `contains` (case-insensitive, in its section title or content).
Labels point at content, not chunk numbers, so they survive re-chunking.

`attack_marker` (optional) marks a prompt-injection test: the string must NOT appear in
the answer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal[
    "factual", "identifier", "comparison", "multi_hop", "unanswerable", "injection"
]


class Expected(BaseModel):
    source: str = Field(min_length=1)
    contains: list[str] = Field(min_length=1)


class EvalItem(BaseModel):
    id: str = Field(min_length=1)
    type: QuestionType
    question: str = Field(min_length=5)
    answerable: bool = True
    expected: list[Expected] = Field(default_factory=list)
    answer_points: list[str] = Field(default_factory=list)
    attack_marker: str | None = None
    split: Literal["dev", "test"] = "dev"

    @model_validator(mode="after")
    def _consistent(self) -> EvalItem:
        if self.answerable and not self.expected:
            raise ValueError(f"{self.id}: an answerable question needs at least one expected entry")
        if not self.answerable and (self.expected or self.answer_points):
            raise ValueError(
                f"{self.id}: an unanswerable question cannot have expected or answer_points"
            )
        if (self.type == "unanswerable") == self.answerable:
            raise ValueError(
                f"{self.id}: type 'unanswerable' and answerable=false must go together"
            )
        if self.type == "injection" and not self.attack_marker:
            raise ValueError(f"{self.id}: an injection question needs an attack_marker")
        return self


def load_dataset(path: Path) -> list[EvalItem]:
    items: list[EvalItem] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            items.append(EvalItem(**json.loads(line)))
        except Exception as exc:
            raise ValueError(f"{path}:{number}: {exc}") from exc
    ids = [item.id for item in items]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"{path}: duplicate ids {duplicates}")
    if not items:
        raise ValueError(f"{path}: no questions")
    return items
