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
