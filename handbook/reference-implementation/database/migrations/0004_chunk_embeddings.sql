-- 0004: chunk embeddings (ADR-017). Runs as rag_owner.
--
-- One row per (chunk, embedding space). The dimension depends on the model (ADR-002), so the column is an
-- unconstrained `vector`; the row records the space, model, recipe and dimension it was produced with, and a
-- CHECK ties the stored vector to the recorded dimension. Component 6 adds approximate indexes per space
-- (expression indexes cast to a fixed dimension); this migration deliberately creates none.
--
-- Access: rag_worker may only INSERT, and only for chunks of a STAGED version of the job's tenant. It cannot
-- read embeddings (a vector is derived content) or update/delete them: replacing chunks removes their
-- embeddings through the foreign key cascade, which referential integrity performs without row security.
-- rag_app may only SELECT, and only for chunks it may see (the chunk ACL applies through the EXISTS).

-- pgvector is not a "trusted" extension, so rag_owner cannot create it: an administrator does, once per
-- database (docker init script 00-extensions.sql; on managed PostgreSQL, allow-list it and run
-- CREATE EXTENSION vector as the admin role). Fail early with a clear message instead of "type does not exist".
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    RAISE EXCEPTION 'the pgvector extension is not installed in this database; an administrator must run CREATE EXTENSION vector';
  END IF;
END $$;

CREATE TABLE rag.chunk_embeddings (
  tenant_id        uuid        NOT NULL,
  chunk_id         uuid        NOT NULL,
  embedding_space  text        NOT NULL CHECK (embedding_space ~ '^[A-Za-z0-9._:-]{1,64}$'),
  model            text        NOT NULL CHECK (length(model) BETWEEN 1 AND 200),
  recipe           text        NOT NULL CHECK (recipe ~ '^[a-z0-9._-]{1,64}$'),
  dimensions       integer     NOT NULL CHECK (dimensions BETWEEN 1 AND 4000),
  embedding        vector      NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, chunk_id, embedding_space),
  FOREIGN KEY (tenant_id, chunk_id) REFERENCES rag.chunks (tenant_id, chunk_id) ON DELETE CASCADE,
  CHECK (vector_dims(embedding) = dimensions)
);

ALTER TABLE rag.chunk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.chunk_embeddings FORCE  ROW LEVEL SECURITY;

GRANT SELECT ON rag.chunk_embeddings TO rag_app;
GRANT INSERT ON rag.chunk_embeddings TO rag_worker;
-- The insert policy must be able to see that the chunk exists; chunk_id is an identifier, not content.
GRANT SELECT (chunk_id) ON rag.chunks TO rag_worker;

CREATE POLICY chunk_embeddings_app_select ON rag.chunk_embeddings FOR SELECT TO rag_app
  USING (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.chunks c
    WHERE c.tenant_id = chunk_embeddings.tenant_id AND c.chunk_id = chunk_embeddings.chunk_id));

-- rag_worker's view of chunks is already limited to staged versions of the job's tenant (0003), so the
-- EXISTS below enforces "staged" as well as "same tenant".
CREATE POLICY chunk_embeddings_worker_insert ON rag.chunk_embeddings FOR INSERT TO rag_worker
  WITH CHECK (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.chunks c
    WHERE c.tenant_id = chunk_embeddings.tenant_id AND c.chunk_id = chunk_embeddings.chunk_id));
