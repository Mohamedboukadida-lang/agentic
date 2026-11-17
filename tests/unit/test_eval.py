import json

import pytest

from ragent.eval import metrics
from ragent.eval.dataset import EvalItem, Expected, load_dataset
from ragent.ingest.chunking import chunk_document
from ragent.ingest.loaders import load_dir
from ragent.models import Chunk
from tests.conftest import ROOT, SAMPLE

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
