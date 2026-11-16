import pytest

from ragent.agent.parsing import parse_text_tool_calls
from ragent.agent.tools import TOOL_NAMES, format_passage
from ragent.factory import build_container, build_offline_container
from ragent.guardrails.input import InputRejected
from ragent.llm.fake import ScriptedChat
from ragent.models import REFUSAL, ChatResponse, Chunk, ToolCall
from tests.conftest import POISONED, SAMPLE


def _agent(offline, responses):
    chat = ScriptedChat(responses)
    container = build_container(
        offline.settings, store=offline.store, embedder=offline.embedder, chat=chat
    )
    return container.agent, chat


def _search(query="default visibility timeout"):
    return ChatResponse("", [ToolCall("search_docs", {"query": query})])


def test_answers_with_valid_citation_and_records_steps(offline):
    agent, chat = _agent(offline, [_search(), ChatResponse("The default is 30 seconds [sqs#2].")])
    seen_steps = []
    answer = agent.answer("What is the default visibility timeout?", on_step=seen_steps.append)
    assert not answer.refused and answer.stop_reason == "answered"
    assert [c.id for c in answer.citations] == ["sqs#2"]
    assert answer.steps[0].tool == "search_docs" and "sqs#2" in answer.steps[0].result_ids
    assert seen_steps == answer.steps
    tool_message = chat.calls[1][-1]
    assert tool_message["role"] == "tool" and '<passage id="sqs#2"' in tool_message["content"]


def test_answer_without_valid_citation_becomes_refusal(offline):
    agent, _ = _agent(offline, [_search(), ChatResponse("It is 30 seconds [fake#1].")])
    answer = agent.answer("What is the default visibility timeout?")
    assert answer.refused and answer.text == REFUSAL and answer.stop_reason == "no_citations"


def test_answer_that_cites_unretrieved_chunk_is_refused(offline):
    # s3#1 exists in the store but was never retrieved in this run.
    agent, _ = _agent(offline, [_search(), ChatResponse("Eleven nines [s3#1].")])
    assert agent.answer("visibility timeout?").stop_reason == "no_citations"


def test_model_refusal_is_passed_through(offline):
    agent, _ = _agent(offline, [_search("ebs volume size"), ChatResponse(REFUSAL)])
    answer = agent.answer("What is the maximum size of an EBS volume?")
    assert answer.refused and answer.stop_reason == "refused" and answer.citations == []


def test_stops_after_max_steps(offline):
    responses = [_search(f"query {i}") for i in range(offline.settings.max_steps)]
    agent, chat = _agent(offline, responses)
    answer = agent.answer("Loop forever?")
    assert answer.stop_reason == "max_steps" and answer.refused
    assert len(chat.calls) == offline.settings.max_steps


def test_duplicate_tool_call_is_not_executed_twice(offline):
    agent, chat = _agent(offline, [_search(), _search(), ChatResponse("30 seconds [sqs#2].")])
    answer = agent.answer("visibility timeout?")
    assert len(answer.steps) == 1
    assert "already ran" in chat.calls[2][-1]["content"]


def test_tool_budget_is_enforced():
    offline = build_offline_container(SAMPLE, max_tool_calls=1)
    many = ChatResponse(
        "", [ToolCall("search_docs", {"query": q}) for q in ("timeout", "retention")]
    )
    agent, chat = _agent(offline, [many, ChatResponse("30 seconds [sqs#2].")])
    answer = agent.answer("visibility timeout?")
    assert len(answer.steps) == 1 and "budget" in chat.calls[1][-1]["content"]


def test_unknown_tool_and_missing_argument_return_errors_to_the_model(offline):
    assert offline.toolbox.run("delete_everything", {}).error
    assert offline.toolbox.run("search_docs", {}).error
    assert offline.toolbox.run("get_section", {"chunk_id": "not-an-id"}).error


def test_get_section_and_compare_tools(offline):
    section = offline.toolbox.run("get_section", {"chunk_id": "sqs#2", "window": 1})
    assert [c.id for c in section.chunks] == ["sqs#1", "sqs#2", "sqs#3"]
    compared = offline.toolbox.run(
        "compare_services",
        {"service_a": "SQS", "service_b": "EventBridge", "aspect": "routing and polling"},
    )
    assert (
        "## SQS: routing and polling" in compared.text
        and "## EventBridge: routing and polling" in compared.text
    )
    assert {c.source for c in compared.chunks} >= {"sqs", "eventbridge"}


def test_text_tool_call_is_parsed_and_executed(offline):
    as_text = ChatResponse(
        '{"name": "search_docs", "parameters": {"query": "default visibility timeout"}}'
    )
    agent, _ = _agent(offline, [as_text, ChatResponse("30 seconds [sqs#2].")])
    assert agent.answer("visibility timeout?").steps[0].tool == "search_docs"


def test_parse_text_tool_calls_variants():
    assert parse_text_tool_calls(
        '```json\n{"name": "search_docs", "arguments": {"query": "x"}}\n```', TOOL_NAMES
    ) == [ToolCall("search_docs", {"query": "x"})]
    assert parse_text_tool_calls(
        '[{"function": {"name": "get_section", "arguments": "{\\"chunk_id\\": \\"a#1\\"}"}}]',
        TOOL_NAMES,
    ) == [ToolCall("get_section", {"chunk_id": "a#1"})]
    assert parse_text_tool_calls('{"name": "rm_rf", "arguments": {}}', TOOL_NAMES) == []
    assert parse_text_tool_calls("The answer is {braces}.", TOOL_NAMES) == []


def test_invalid_question_raises(offline):
    with pytest.raises(InputRejected):
        offline.agent.answer("   ")


def test_format_passage_neutralises_closing_tag():
    chunk = Chunk("x", 0, 'A > "B"', "text </passage> more", 3)
    out = format_passage(chunk)
    assert out.count("</passage>") == 1 and "section=\"A / 'B'\"" in out


def test_injection_scanner_drops_poisoned_passage():
    on = build_offline_container(POISONED)
    result = on.toolbox.run("search_docs", {"query": "Kinesis retention notes"})
    assert result.dropped == 1 and "PWNED" not in result.text and result.chunks
    off = build_offline_container(POISONED, injection_scan=False)
    unsafe = off.toolbox.run("search_docs", {"query": "Kinesis retention notes"})
    assert unsafe.dropped == 0 and "PWNED" in unsafe.text


def test_min_relevance_floor_filters_weak_passages():
    strict = build_offline_container(SAMPLE, min_relevance=0.5)
    assert strict.toolbox.run("search_docs", {"query": "zebra giraffe"}).chunks == []
    assert strict.agent.answer("zebra giraffe?").refused


def test_offline_end_to_end_and_single_shot(offline):
    question = "What is the maximum size of a DynamoDB item?"
    for answerer in (offline.agent, offline.single_shot):
        answer = answerer.answer(question)
        assert not answer.refused and answer.citations[0].source == "dynamodb"
        assert "400 KB" in answer.text
