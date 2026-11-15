"""PostgreSQL + pgvector store.

Opens one connection per call. That is simple and correct; a connection pool
(psycopg_pool) is the first thing to add if latency matters.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ragent.models import Chunk, Document
from ragent.text import content_terms

_COLUMNS = "d.source, c.ordinal, c.section, c.content, c.token_count"
_FROM = "FROM chunks c JOIN documents d ON d.id = c.document_id"


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vector) + "]"


def _chunk(row: tuple[Any, ...]) -> Chunk:
    return Chunk(source=row[0], ordinal=row[1], section=row[2], content=row[3], token_count=row[4])


def build_tsquery(query: str) -> str:
    """OR the content words of the question: 'default visibility timeout' ->
    'default | visibility | timeout'. websearch_to_tsquery would AND them, which matches
    almost nothing for a natural-language question. Tokens are [a-z0-9]+ only, so the
    string is safe to pass to to_tsquery."""
    return " | ".join(content_terms(query, stem=False))


class PgVectorStore:
    def __init__(self, dsn: str) -> None:
        import psycopg  # lazy: only needed when this store is used

        self._psycopg = psycopg
        self._dsn = dsn

    def _connect(self) -> Any:
        return self._psycopg.connect(self._dsn)

    def upsert_document(
        self, doc: Document, content_hash: str, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings differ in length")
        with self._connect() as conn, conn.cursor() as cur:  # commits on success
            cur.execute(
                """
                INSERT INTO documents (source, title, content_hash, metadata)
                VALUES (%s, %s, %s, %s::jsonb)
                ON CONFLICT (source) DO UPDATE
                  SET title = EXCLUDED.title, content_hash = EXCLUDED.content_hash,
                      metadata = EXCLUDED.metadata, ingested_at = now()
                RETURNING id
                """,
                (doc.source, doc.title, content_hash, json.dumps(doc.metadata)),
            )
            document_id = cur.fetchone()[0]
            cur.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
            cur.executemany(
                """
                INSERT INTO chunks (document_id, ordinal, section, content, token_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                """,
                [
                    (
                        document_id,
                        c.ordinal,
                        c.section,
                        c.content,
                        c.token_count,
                        _vector_literal(e),
                    )
                    for c, e in zip(chunks, embeddings, strict=True)
                ],
            )

    def document_hash(self, source: str) -> str | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM documents WHERE source = %s", (source,))
            row = cur.fetchone()
            return row[0] if row else None

    def count(self) -> int:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM chunks")
            return int(cur.fetchone()[0])

    def vector_search(self, embedding: list[float], k: int) -> list[tuple[Chunk, float]]:
        literal = _vector_literal(embedding)
        with self._connect() as conn, conn.cursor() as cur:
            # <=> is cosine distance; similarity = 1 - distance.
            cur.execute(
                f"""
                SELECT {_COLUMNS}, 1 - (c.embedding <=> %s::vector) AS score
                {_FROM}
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
                """,
                (literal, literal, k),
            )
            return [(_chunk(row), float(row[5])) for row in cur.fetchall()]

    def keyword_search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        tsquery = build_tsquery(query)
        if not tsquery:
            return []
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS}, ts_rank_cd(c.tsv, q) AS score
                {_FROM}, to_tsquery('english', %s) AS q
                WHERE c.tsv @@ q
                ORDER BY score DESC, c.id
                LIMIT %s
                """,
                (tsquery, k),
            )
            return [(_chunk(row), float(row[5])) for row in cur.fetchall()]

    def get_chunk(self, source: str, ordinal: int) -> Chunk | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT {_COLUMNS} {_FROM} WHERE d.source = %s AND c.ordinal = %s",
                (source, ordinal),
            )
            row = cur.fetchone()
            return _chunk(row) if row else None

    def neighbours(self, source: str, ordinal: int, window: int) -> list[Chunk]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT {_COLUMNS} {_FROM}
                WHERE d.source = %s AND c.ordinal BETWEEN %s AND %s
                ORDER BY c.ordinal
                """,
                (source, ordinal - window, ordinal + window),
            )
            return [_chunk(row) for row in cur.fetchall()]


def apply_migrations(dsn: str, directory: Path) -> list[str]:
    """Run every .sql file in `directory` that has not been applied yet, in name order."""
    import psycopg

    applied: list[str] = []
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cur.execute("SELECT filename FROM schema_migrations")
        done = {row[0] for row in cur.fetchall()}
        for path in sorted(directory.glob("*.sql")):
            if path.name in done:
                continue
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            applied.append(path.name)
    return applied
