import pytest
from pydantic import ValidationError

from ragent.config import Settings
from ragent.text import content_terms, count_tokens, normalize, tokenize


def test_tokenize_keeps_identifiers_whole():
    assert tokenize("Set ReceiveMessageWaitTimeSeconds=20") == [
        "set",
        "receivemessagewaittimeseconds",
        "20",
    ]


def test_normalize_strips_simple_plurals_only():
    assert normalize("queues") == "queue"
    assert normalize("policies") == "policy"
    assert normalize("sqs") == "sqs"  # short tokens are left alone
    assert normalize("access") == "access"
    assert normalize("kinesis") == "kinesis"


def test_content_terms_drops_stopwords_and_duplicates():
    assert content_terms("What is the default timeout of the queue and the queues?") == [
        "default",
        "timeout",
        "queue",
    ]


def test_count_tokens_counts_words():
    assert count_tokens("one two  three\nfour") == 4


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("RAGENT_TOP_K", "3")
    monkeypatch.setenv("RAGENT_INJECTION_SCAN", "false")
    s = Settings.from_env(reranker="none")
    assert (s.top_k, s.injection_scan, s.reranker) == (3, False, "none")


@pytest.mark.parametrize(
    "bad",
    [
        {"chunk_tokens": 50, "chunk_overlap": 50},
        {"top_k": 30},
        {"reranker": "magic"},
        {"store": "sqlite"},
    ],
)
def test_settings_reject_bad_values(bad):
    with pytest.raises(ValidationError):
        Settings(**bad)
