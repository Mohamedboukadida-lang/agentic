"""The agent loop.

    question -> [model -> tool calls -> tool results]* -> answer -> validation

Stop rules:
  * at most settings.max_steps model turns
  * at most settings.max_tool_calls executed tool calls
  * an identical tool call is not executed twice
The answer must cite at least one chunk retrieved in this run, otherwise it becomes the
fixed refusal.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from ragent.agent.parsing import parse_text_tool_calls
from ragent.agent.prompts import SYSTEM_PROMPT
from ragent.agent.tools import TOOL_NAMES, TOOL_SCHEMAS, Toolbox
from ragent.config import Settings
from ragent.guardrails.input import validate_question
from ragent.guardrails.output import is_refusal, validate_answer
from ragent.llm.base import ChatModel, Message
from ragent.models import REFUSAL, Answer, Chunk, Citation, Step
from ragent.observability.tracing import Tracer

StepCallback = Callable[[Step], None]


class Agent:
    def __init__(self, chat: ChatModel, toolbox: Toolbox, settings: Settings) -> None:
        self._chat = chat
        self._toolbox = toolbox
        self._settings = settings

    def answer(self, question: str, on_step: StepCallback | None = None) -> Answer:
        """Raises guardrails.input.InputRejected if the question fails validation."""
        s = self._settings
        tracer = Tracer()
        question = validate_question(question, s.max_question_chars)
        messages: list[Message] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        seen: dict[str, Chunk] = {}
        steps: list[Step] = []
        executed: set[str] = set()
        dropped = 0
        final: str | None = None

        for turn in range(s.max_steps):
            with tracer.span("chat", turn=turn):
                response = self._chat.chat(messages, tools=TOOL_SCHEMAS)
            calls = response.tool_calls or parse_text_tool_calls(response.content, TOOL_NAMES)
            if not calls:
                final = response.content.strip()
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content if response.tool_calls else "",
                    "tool_calls": [
                        {"function": {"name": c.name, "arguments": c.arguments}} for c in calls
                    ],
                }
            )
            for call in calls:
                key = call.name + json.dumps(call.arguments, sort_keys=True, default=str)
                if key in executed:
                    text = "You already ran this exact call. Use the earlier result."
                elif len(executed) >= s.max_tool_calls:
                    text = "Tool budget used up. Answer from the passages you have, or refuse."
                else:
                    executed.add(key)
                    started = time.perf_counter()
                    with tracer.span("tool", tool=call.name):
                        result = self._toolbox.run(call.name, call.arguments)
                    seen.update({chunk.id: chunk for chunk in result.chunks})
                    dropped += result.dropped
                    text = result.text[: s.tool_output_chars]
                    step = Step(
                        tool=call.name,
                        arguments=call.arguments,
                        result_ids=[chunk.id for chunk in result.chunks],
                        ms=round((time.perf_counter() - started) * 1000),
                        note="error" if result.error else "",
                    )
                    steps.append(step)
                    if on_step:
                        on_step(step)
                messages.append({"role": "tool", "tool_name": call.name, "content": text})

        text, citations, stop_reason = self._finish(final, seen)
        answer = Answer(
            text=text,
            refused=stop_reason != "answered",
            citations=citations,
            steps=steps,
            trace_id=tracer.trace_id,
            latency_ms=tracer.elapsed_ms(),
            dropped_passages=dropped,
            stop_reason=stop_reason,
        )
        tracer.emit(stop_reason=stop_reason, tool_calls=len(steps), dropped_passages=dropped)
        return answer

    def _finish(self, final: str | None, seen: dict[str, Chunk]) -> tuple[str, list[Citation], str]:
        if final is None:
            return REFUSAL, [], "max_steps"
        if is_refusal(final):
            return REFUSAL, [], "refused"
        cleaned, valid_ids = validate_answer(final, seen, self._settings.max_answer_chars)
        if not valid_ids:
            return REFUSAL, [], "no_citations"
        citations = [Citation(i, seen[i].source, seen[i].section) for i in valid_ids]
        return cleaned, citations, "answered"
