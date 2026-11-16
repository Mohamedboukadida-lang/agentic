"""A minimal tracer: one trace per question, one span per step, emitted as a JSON log line.

    tracer = Tracer()
    with tracer.span("chat", model="llama3.1:8b"):
        ...
    tracer.emit(question_chars=42)

Output goes to the 'ragent.trace' logger. To export to OpenTelemetry or Langfuse later,
replace emit(); the call sites stay the same.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_log = logging.getLogger("ragent.trace")


class Tracer:
    def __init__(self) -> None:
        self.trace_id = uuid.uuid4().hex[:12]
        self.spans: list[dict[str, Any]] = []
        self._start = time.perf_counter()

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[dict[str, Any]]:
        record: dict[str, Any] = {"name": name, **attributes}
        started = time.perf_counter()
        try:
            yield record
        except Exception as exc:
            record["error"] = type(exc).__name__
            raise
        finally:
            record["ms"] = round((time.perf_counter() - started) * 1000)
            self.spans.append(record)

    def elapsed_ms(self) -> int:
        return round((time.perf_counter() - self._start) * 1000)

    def emit(self, **attributes: Any) -> None:
        _log.info(
            json.dumps(
                {
                    "trace_id": self.trace_id,
                    "ms": self.elapsed_ms(),
                    **attributes,
                    "spans": self.spans,
                },
                default=str,
            )
        )
