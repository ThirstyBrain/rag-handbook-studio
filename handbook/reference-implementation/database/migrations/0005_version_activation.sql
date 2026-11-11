-- 0005: version activation (ADR-019). Runs as rag_owner.  STATUS: AUTHORED, NOT EXECUTED (no database was
-- available when this was written; see project-management/QUALITY-REPORT.md).
--
-- Until now no code path moved a version from 'staged' to 'active', so no chunk was ever retrievable.
-- Activation is the last step of the ingest job, in the SAME transaction that stores the chunks and vectors
-- (ChunkStore.replace_chunks), so a version becomes visible to retrieval only when it is complete.
--
-- Database-level guards (the worker is trusted code for integrity, not for confidentiality):
--   * at most one ACTIVE version per document (partial unique index);
--   * rag_worker may move a STAGED version to ACTIVE only if the version has at least one chunk;
--   * rag_worker may move an ACTIVE version to SUPERSEDED, and nothing else about active versions;
--   * the worker still cannot read content, vectors or other tenants' rows.
-- "Every chunk has a vector" is enforced by the application inside the same transaction (it just wrote them);
-- a policy cannot express it without giving the worker SELECT on chunk_embeddings, which ADR-017 withholds.

CREATE UNIQUE INDEX document_versions_one_active
  ON rag.document_versions (tenant_id, document_id)
  WHERE state = 'active';

-- Permissive policies are OR-ed with versions_worker_update (staged -> staged|failed, from 0003).
CREATE POLICY versions_worker_activate ON rag.document_versions FOR UPDATE TO rag_worker
  USING (tenant_id = rag.app_tenant() AND state = 'staged')
  WITH CHECK (
    tenant_id = rag.app_tenant()
    AND state = 'active'
    AND EXISTS (
      SELECT 1 FROM rag.chunks c
      WHERE c.tenant_id = document_versions.tenant_id
        AND c.document_id = document_versions.document_id
        AND c.version = document_versions.version));

CREATE POLICY versions_worker_supersede ON rag.document_versions FOR UPDATE TO rag_worker
  USING (tenant_id = rag.app_tenant() AND state = 'active')
  WITH CHECK (tenant_id = rag.app_tenant() AND state = 'superseded');
