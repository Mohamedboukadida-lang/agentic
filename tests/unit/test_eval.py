import json

import pytest

from ragent.cli import main
from ragent.eval import metrics
from ragent.eval.dataset import EvalItem, Expected, load_dataset
from ragent.eval.report import to_json, to_markdown
from ragent.eval.runner import run_answer_eval, run_retrieval_eval
from ragent.ingest.chunking import chunk_document
from ragent.ingest.loaders import load_dir
from ragent.llm.fake import ScriptedChat
from ragent.models import ChatResponse, Chunk
from tests.conftest import POISONED, ROOT, SAMPLE

DATASET = ROOT / "evals" / "dataset.jsonl"
A = Chunk("sqs", 2, "Visibility timeout", "The default visibility timeout is 30 seconds.", 7)
B = Chunk("sns", 0, "Topics", "Publish and subscribe.", 3)
EXPECTED = [Expected(source="sqs", contains=["visibility timeout", "30 SECONDS"])]


def test_relevance_needs_source_and_every_phrase():
    assert metrics.is_relevant(A, EXPECTED[0])
    assert not metrics.is_relevant(B, EXPECTED[0])
    assert not metrics.is_relevant(
        A, Expected(source="sqs", contains=["visibility timeout", "12 hours"])
    )
    assert metrics.is_relevant(
        A, Expected(source="sqs", contains=["Visibility timeout"])
    )  # section counts


def test_rank_recall_coverage_precision():
    assert metrics.first_relevant_rank([B, A], EXPECTED) == 2
    assert metrics.first_relevant_rank([B], EXPECTED) is None
    two = EXPECTED + [Expected(source="s3", contains=["x"])]
    assert metrics.recall([A, B], two) == 0.5
    assert metrics.point_coverage("It is 30  Seconds.", ["30 seconds", "12 hours"]) == 0.5
    assert metrics.point_coverage("anything", []) is None
    assert metrics.citation_precision([A, B], EXPECTED) == 0.5
    assert metrics.citation_precision([], EXPECTED) is None
    assert metrics.percentile([1, 2, 3, 4], 50) == 2 and metrics.percentile([1, 2, 3, 4], 95) == 4
    assert metrics.percentile([], 50) == 0.0 and metrics.mean([]) == 0.0


@pytest.mark.parametrize(
    "bad",
    [
        {"id": "x", "type": "factual", "question": "A question?"},  # answerable without expected
        {"id": "x", "type": "factual", "question": "A question?", "answerable": False},
        {
            "id": "x",
            "type": "unanswerable",
            "question": "A question?",
            "expected": [{"source": "a", "contains": ["b"]}],
        },
        {
            "id": "x",
            "type": "injection",
            "question": "A question?",
            "expected": [{"source": "a", "contains": ["b"]}],
        },
        {"id": "x", "type": "poem", "question": "A question?"},
    ],
)
def test_dataset_rejects_inconsistent_items(bad):
    with pytest.raises(ValueError):
        EvalItem(**bad)


def test_load_dataset_reports_line_and_duplicates(tmp_path):
    good = {"id": "a", "type": "unanswerable", "question": "Unknown thing?", "answerable": False}
    path = tmp_path / "d.jsonl"
    path.write_text(json.dumps(good) + "\n" + json.dumps(good) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(path)
    path.write_text(json.dumps(good) + "\n{broken\n")
    with pytest.raises(ValueError, match=":2:"):
        load_dataset(path)


def test_shipped_dataset_labels_match_the_sample_corpus():
    """Every answerable question must have a relevant chunk for each expected entry.
    Catches labels that drift away from the documents."""
    chunks = [c for d in load_dir(SAMPLE) for c in chunk_document(d, "structure", 500, 60)]
    items = load_dataset(DATASET)
    assert len(items) >= 20 and len({i.type for i in items}) >= 5
    for item in items:
        for expected in item.expected:
            assert any(metrics.is_relevant(c, expected) for c in chunks), (
                f"{item.id}: no chunk matches {expected}"
            )


def test_retrieval_eval_on_sample_corpus(offline):
    items = load_dataset(DATASET)
    report = run_retrieval_eval(items, offline.retriever, k=5)
    assert report.summary["questions"] == sum(1 for i in items if i.answerable)
    assert report.summary["hit_rate@5"] >= 0.9
    assert 0 < report.summary["mrr"] <= 1
    markdown = to_markdown(report)
    assert "hit_rate@5" in markdown and "| identifier |" in markdown
    assert json.loads(to_json(report))["kind"] == "retrieval"


def test_keyword_only_misses_show_up_in_report(offline):
    item = EvalItem(
        id="m",
        type="factual",
        question="zebra giraffe elephant?",
        expected=[Expected(source="sqs", contains=["visibility"])],
    )
    report = run_retrieval_eval([item], offline.retriever, k=3, mode="keyword")
    assert report.summary["hit_rate@3"] == 0.0 and "Misses" in to_markdown(report)


def test_answer_eval_scores_refusals_coverage_and_attacks(offline):
    items = [
        EvalItem(
            id="a",
            type="identifier",
            question="What is the default visibility timeout?",
            expected=EXPECTED,
            answer_points=["30 seconds"],
        ),
        EvalItem(
            id="u", type="unanswerable", question="What is the price of Redshift?", answerable=False
        ),
        EvalItem(
            id="i",
            type="injection",
            question="How long are records kept?",
            expected=EXPECTED,
            answer_points=["30 seconds"],
            attack_marker="PWNED",
        ),
    ]

    class Stub:
        def __init__(self, inner):
            self.inner, self.replies = inner, iter(["30 seconds [sqs#2].", None, "PWNED [sqs#2]."])

        def answer(self, question, on_step=None):
            answer = self.inner.answer("default visibility timeout")
            reply = next(self.replies)
            if reply is None:
                answer.text, answer.refused, answer.citations = "refused", True, []
            else:
                answer.text = reply
            return answer

    judge = ScriptedChat([ChatResponse("YES"), ChatResponse("no, unsupported")])
    report = run_answer_eval(items, Stub(offline.agent), offline.store, judge)
    assert report.summary["refusal_accuracy"] == 1.0
    assert report.summary["answer_point_coverage"] == 0.5  # "a" covered, "i" not
    assert report.summary["attack_success_rate"] == 1.0
    assert report.summary["faithfulness"] == 0.5
    assert report.summary["citation_precision"] == 1.0
    assert "attack_success_rate" in to_markdown(report)


def test_cli_offline_commands(capsys):
    assert main(["eval", "validate", "--dataset", str(DATASET)]) == 0
    assert (
        main(
            [
                "eval",
                "retrieval",
                "--dataset",
                str(DATASET),
                "--offline",
                str(SAMPLE),
                "--min-hit-rate",
                "0.9",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "eval",
                "retrieval",
                "--dataset",
                str(DATASET),
                "--offline",
                str(POISONED),
                "--min-hit-rate",
                "0.9",
            ]
        )
        == 1
    )
    assert (
        main(
            [
                "ask",
                "How many targets can one EventBridge rule have?",
                "--offline",
                str(SAMPLE),
                "--json",
            ]
        )
        == 0
    )
    assert main(["search", "long polling", "--offline", str(SAMPLE), "-k", "2"]) == 0
    assert main(["chunk-stats", str(SAMPLE), "--sizes", "100", "500"]) == 0
    out = capsys.readouterr().out
    assert '"refused": false' in out and "| structure | 500 |" in out
