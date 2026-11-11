-- 0002: ingestion job queue (Postgres-backed; ADR-015).
-- Runs as rag_owner. Adds the third role's access: rag_worker (created at cluster bootstrap) may read and
-- update JOBS ONLY. It has no grant on any content table, so a compromised worker cannot read documents.
--
-- Queue semantics (implemented in rag_service/jobs/queue.py):
--   claim   : SELECT ... FOR UPDATE SKIP LOCKED, sets state=running, attempts+1, a lease and locked_by
--   success : state=succeeded (only by the lease holder)
--   failure : state=queued with run_after = now + backoff, or state=dead once attempts reach max_attempts
--   crash   : an expired lease makes a running job claimable again (counts as an attempt)
-- No foreign key to documents: a delete_objects job must outlive the document it cleans up after.

GRANT USAGE ON SCHEMA rag TO rag_worker;

CREATE TABLE rag.ingestion_jobs (
  job_id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id         uuid        NOT NULL REFERENCES rag.tenants ON DELETE CASCADE,
  kind              text        NOT NULL CHECK (kind IN ('ingest_version', 'delete_objects')),
  document_id       uuid,
  version           integer     CHECK (version IS NULL OR version >= 1),
  payload           jsonb       NOT NULL DEFAULT '{}'::jsonb,
  state             text        NOT NULL DEFAULT 'queued'
                    CHECK (state IN ('queued', 'running', 'succeeded', 'dead', 'cancelled')),
  attempts          integer     NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts      integer     NOT NULL DEFAULT 5 CHECK (max_attempts BETWEEN 1 AND 20),
  run_after         timestamptz NOT NULL DEFAULT now(),
  lease_expires_at  timestamptz,
  locked_by         text,
  last_error        text,      -- an exception CLASS name only: never messages, which can hold data
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ingestion_jobs_claim ON rag.ingestion_jobs (run_after, created_at)
  WHERE state IN ('queued', 'running');
CREATE INDEX ingestion_jobs_tenant ON rag.ingestion_jobs (tenant_id, created_at DESC);

ALTER TABLE rag.ingestion_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.ingestion_jobs FORCE  ROW LEVEL SECURITY;

-- The API can enqueue jobs for its own tenant and read its own tenant's jobs (status), nothing else.
CREATE POLICY jobs_app_select ON rag.ingestion_jobs FOR SELECT TO rag_app
  USING (tenant_id = rag.app_tenant());
CREATE POLICY jobs_app_insert ON rag.ingestion_jobs FOR INSERT TO rag_app
  WITH CHECK (tenant_id = rag.app_tenant());
-- The worker works across tenants but only on this table, and only through these policies.
CREATE POLICY jobs_worker_all ON rag.ingestion_jobs FOR ALL TO rag_worker
  USING (true) WITH CHECK (true);

GRANT SELECT, INSERT ON rag.ingestion_jobs TO rag_app;
GRANT SELECT, UPDATE ON rag.ingestion_jobs TO rag_worker;
