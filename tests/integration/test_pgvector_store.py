"""Runs against a real PostgreSQL with pgvector.

make up && make migrate
RAGENT_DATABASE_URL=postgresql://ragent:ragent@localhost:5432/ragent pytest -m integration
"""

import os

import pytest

from ragent.config import Settings
from ragent.ingest.loaders import load_dir
from ragent.ingest.pipeline import ingest_documents
from ragent.llm.fake import FakeEmbedder
from tests.conftest import ROOT, SAMPLE

pytestmark = pytest.mark.integration
DSN = os.environ.get("RAGENT_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def dsn():
    if not DSN:
        pytest.skip("set RAGENT_DATABASE_URL to run integration tests")
    return DSN


@pytest.fixture(scope="module")
def store(dsn):
    pytest.importorskip("psycopg")
    from ragent.store.pgvector import PgVectorStore, apply_migrations

    apply_migrations(dsn, ROOT / "db" / "migrations")
    store = PgVectorStore(dsn)
    # FakeEmbedder at 768 dimensions matches the vector(768) column.
    ingest_documents(load_dir(SAMPLE), store, FakeEmbedder(768), Settings(embed_dim=768))
    return store


def test_migrations_are_idempotent(dsn, store):
    from ragent.store.pgvector import apply_migrations

    assert apply_migrations(dsn, ROOT / "db" / "migrations") == []


def test_vector_and_keyword_search(store):
    query = "default visibility timeout"
    assert store.count() > 0
    vector_hits = store.vector_search(FakeEmbedder(768).embed_query(query), 3)
    keyword_hits = store.keyword_search(query, 3)
    assert vector_hits[0][0].section.endswith("Visibility timeout")
    assert keyword_hits and keyword_hits[0][0].source == "sqs"
    assert store.keyword_search("the of and", 3) == []


def test_chunk_lookup_and_reingest_skips(store):
    assert store.get_chunk("sqs", 2).id == "sqs#2"
    assert [c.ordinal for c in store.neighbours("sqs", 2, 1)] == [1, 2, 3]
    stats = ingest_documents(load_dir(SAMPLE), store, FakeEmbedder(768), Settings(embed_dim=768))
    assert stats.documents == 0 and stats.skipped == 6
