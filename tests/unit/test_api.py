import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ragent.api.app import create_app  # noqa: E402


@pytest.fixture
def client(offline):
    return TestClient(create_app(offline))


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["chunks"] > 0 and body["store"] == "memory"


def test_search(client):
    results = client.post("/search", json={"query": "default visibility timeout", "k": 2}).json()[
        "results"
    ]
    assert len(results) == 2 and results[0]["id"].startswith("sqs#")
    assert client.post("/search", json={"query": "", "k": 2}).status_code == 422


def test_ask_and_validation(client):
    body = client.post(
        "/ask", json={"question": "What is the maximum size of a DynamoDB item?"}
    ).json()
    assert body["refused"] is False and body["citations"][0]["source"] == "dynamodb"
    assert client.post("/ask", json={"question": "   "}).status_code == 422


def test_ask_stream_sends_step_answer_done(client):
    with client.stream(
        "POST", "/ask/stream", json={"question": "How many targets can one EventBridge rule have?"}
    ) as r:
        text = "".join(r.iter_text())
    events = [line.split(": ", 1)[1] for line in text.splitlines() if line.startswith("event: ")]
    assert events == ["step", "answer", "done"]
