-- 0003: extraction and chunking (ADR-016).
-- Runs as rag_owner.
--
-- 1. Chunk lineage and failure bookkeeping columns.
-- 2. FIX: the 0001 policies had no TO clause, so they applied to PUBLIC, i.e. to every role including any
--    role added later. Permissive policies are OR-ed, so adding rag_worker's policies below would have
--    been widened by them. Every policy is now bound to the role it was written for. A guard test
--    (test_schema_security.py) fails if any policy in schema rag applies to PUBLIC.
-- 3. rag_worker gets a deliberately narrow content path: it can WRITE chunks of a STAGED version of the
--    tenant named by the job it is processing, and mark that version failed. It cannot read chunk
--    content, document titles or anything of another tenant, and it cannot activate a version.

ALTER TABLE rag.chunks
  ADD COLUMN page_start integer CHECK (page_start IS NULL OR page_start >= 1),
  ADD COLUMN page_end   integer CHECK (page_end IS NULL OR page_end >= page_start),
  ADD COLUMN chunker    text    NOT NULL DEFAULT '';

ALTER TABLE rag.document_versions
  ADD COLUMN failure_reason text
    CHECK (failure_reason IS NULL OR failure_reason ~ '^[a-z_]{1,64}$');

-- ---------------------------------------------------------------- bind existing policies to rag_app
ALTER POLICY tenants_select   ON rag.tenants           TO rag_app;
ALTER POLICY documents_select ON rag.documents         TO rag_app;
ALTER POLICY documents_insert ON rag.documents         TO rag_app;
ALTER POLICY documents_update ON rag.documents         TO rag_app;
ALTER POLICY documents_delete ON rag.documents         TO rag_app;
ALTER POLICY versions_select  ON rag.document_versions TO rag_app;
ALTER POLICY versions_insert  ON rag.document_versions TO rag_app;
ALTER POLICY versions_update  ON rag.document_versions TO rag_app;
ALTER POLICY versions_delete  ON rag.document_versions TO rag_app;
ALTER POLICY chunks_select    ON rag.chunks            TO rag_app;
ALTER POLICY chunks_insert    ON rag.chunks            TO rag_app;
ALTER POLICY chunks_update    ON rag.chunks            TO rag_app;
ALTER POLICY chunks_delete    ON rag.chunks            TO rag_app;

-- ---------------------------------------------------------------- the worker's narrow content path
-- Column-level grants: the worker never receives a privilege on chunks.content, documents.title, etc.
GRANT SELECT (tenant_id, document_id, status, acl_groups) ON rag.documents TO rag_worker;
GRANT SELECT (tenant_id, document_id, version, state) ON rag.document_versions TO rag_worker;
GRANT UPDATE (state, extractor, failure_reason) ON rag.document_versions TO rag_worker;
GRANT SELECT (tenant_id, document_id, version) ON rag.chunks TO rag_worker;  -- needed by DELETE ... WHERE
GRANT INSERT, DELETE ON rag.chunks TO rag_worker;

-- The worker sets app.tenant_id from the job row it holds (transaction-local, like the API does).
CREATE POLICY documents_worker_select ON rag.documents FOR SELECT TO rag_worker
  USING (tenant_id = rag.app_tenant());
CREATE POLICY versions_worker_select ON rag.document_versions FOR SELECT TO rag_worker
  USING (tenant_id = rag.app_tenant());
-- It can touch only STAGED versions and can only leave them staged or failed (never active).
CREATE POLICY versions_worker_update ON rag.document_versions FOR UPDATE TO rag_worker
  USING (tenant_id = rag.app_tenant() AND state = 'staged')
  WITH CHECK (tenant_id = rag.app_tenant() AND state IN ('staged', 'failed'));
CREATE POLICY chunks_worker_select ON rag.chunks FOR SELECT TO rag_worker
  USING (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.document_versions v
    WHERE v.tenant_id = chunks.tenant_id AND v.document_id = chunks.document_id
      AND v.version = chunks.version AND v.state = 'staged'));
CREATE POLICY chunks_worker_insert ON rag.chunks FOR INSERT TO rag_worker
  WITH CHECK (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.document_versions v
    WHERE v.tenant_id = chunks.tenant_id AND v.document_id = chunks.document_id
      AND v.version = chunks.version AND v.state = 'staged'));
CREATE POLICY chunks_worker_delete ON rag.chunks FOR DELETE TO rag_worker
  USING (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.document_versions v
    WHERE v.tenant_id = chunks.tenant_id AND v.document_id = chunks.document_id
      AND v.version = chunks.version AND v.state = 'staged'));
