-- Schema for ragent. Applied by `ragent migrate` (see src/ragent/store/pgvector.py).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id           BIGSERIAL PRIMARY KEY,
  source       TEXT NOT NULL UNIQUE,            -- short id of the file, e.g. "sqs"
  title        TEXT NOT NULL,
  content_hash TEXT NOT NULL,                   -- sha256 of text + chunking settings
  metadata     JSONB NOT NULL DEFAULT '{}',
  ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
  id          BIGSERIAL PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  ordinal     INT NOT NULL,                     -- position inside the document
  section     TEXT NOT NULL DEFAULT '',         -- heading path
  content     TEXT NOT NULL,
  token_count INT NOT NULL,
  embedding   vector(768) NOT NULL,             -- must match RAGENT_EMBED_DIM
  tsv         tsvector GENERATED ALWAYS AS (
                to_tsvector('english', section || ' ' || content)
              ) STORED,
  UNIQUE (document_id, ordinal)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
  ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin
  ON chunks USING gin (tsv);
