import json

import pytest

from ragent.eval.dataset import EvalItem, load_dataset


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
