-- 0001: core multi-tenant schema, row-level security, least-privilege grants.
-- Runs as the owner role (rag_owner). Roles are created at cluster bootstrap (database/init/10-roles.sh):
--   rag_owner  owns the objects, runs migrations; not a superuser, no BYPASSRLS
--   rag_app    what the API connects as; DML only, no DDL, no BYPASSRLS
-- Verified patterns: scripts/verify-sql/03-rls.sql (RLS, FORCE, WITH CHECK, transaction-local identity)
-- and 04-hybrid-fts-schema.sql (partial unique index so reverting A -> B -> A is allowed).
--
-- Identity is supplied per transaction by the application with set_config(..., true):
--   app.tenant_id (uuid), app.user_id (text), app.groups (JSON array of text)
-- Missing or empty identity makes every policy raise an error: the database fails closed.

GRANT USAGE ON SCHEMA rag TO rag_app;

CREATE FUNCTION rag.app_tenant() RETURNS uuid
  LANGUAGE sql STABLE
  AS $$ SELECT current_setting('app.tenant_id')::uuid $$;

CREATE FUNCTION rag.app_groups() RETURNS text[]
  LANGUAGE sql STABLE
  AS $$ SELECT COALESCE(ARRAY(SELECT jsonb_array_elements_text(current_setting('app.groups')::jsonb)),
                        '{}'::text[]) $$;

-- ---------------------------------------------------------------- tenants
CREATE TABLE rag.tenants (
  tenant_id   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text        NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
  status      text        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (name)
);

-- ---------------------------------------------------------------- documents
-- Every tenant-owned table carries tenant_id and uses it in its keys, so composite foreign keys make a
-- cross-tenant reference impossible by constraint (foreign-key checks bypass RLS, so this matters).
CREATE TABLE rag.documents (
  tenant_id       uuid        NOT NULL REFERENCES rag.tenants ON DELETE CASCADE,
  document_id     uuid        NOT NULL DEFAULT gen_random_uuid(),
  source_id       text        NOT NULL CHECK (length(source_id) BETWEEN 1 AND 1000),
  title           text        NOT NULL DEFAULT '',
  classification  text        NOT NULL DEFAULT 'internal'
                  CHECK (classification IN ('public', 'internal', 'restricted')),
  status          text        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deleted')),
  current_version integer     CHECK (current_version IS NULL OR current_version >= 1),
  -- a document with no ACL group would be invisible to everyone: reject it
  acl_groups      text[]      NOT NULL CHECK (cardinality(acl_groups) > 0),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, document_id),
  UNIQUE (tenant_id, source_id)
);

CREATE TABLE rag.document_versions (
  tenant_id       uuid        NOT NULL,
  document_id     uuid        NOT NULL,
  version         integer     NOT NULL CHECK (version >= 1),
  content_sha256  text        NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  raw_object_uri  text        NOT NULL,
  extractor       text        NOT NULL,
  state           text        NOT NULL CHECK (state IN ('staged', 'active', 'superseded', 'failed')),
  ingested_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, document_id, version),
  FOREIGN KEY (tenant_id, document_id) REFERENCES rag.documents ON DELETE CASCADE
);
-- At most one LIVE (staged or active) version per content hash; superseded ones are outside the index,
-- so A -> B -> A reverts are accepted while re-ingesting the current content is idempotent.
CREATE UNIQUE INDEX document_versions_live_hash
  ON rag.document_versions (tenant_id, document_id, content_sha256)
  WHERE state IN ('staged', 'active');

-- ---------------------------------------------------------------- chunks
-- Embeddings are stored separately (component 6) because their dimension depends on the model (ADR-002).
CREATE TABLE rag.chunks (
  tenant_id     uuid        NOT NULL,
  chunk_id      uuid        NOT NULL DEFAULT gen_random_uuid(),
  document_id   uuid        NOT NULL,
  version       integer     NOT NULL,
  ordinal       integer     NOT NULL CHECK (ordinal >= 0),
  content       text        NOT NULL CHECK (length(content) > 0),
  section_path  text        NOT NULL DEFAULT '',
  token_count   integer     NOT NULL DEFAULT 0 CHECK (token_count >= 0),
  acl_groups    text[]      NOT NULL CHECK (cardinality(acl_groups) > 0),
  -- 'english' is the reference default; per-tenant language configuration is future work (Chapter 9)
  fts           tsvector    GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, chunk_id),
  UNIQUE (tenant_id, document_id, version, ordinal),
  FOREIGN KEY (tenant_id, document_id, version)
    REFERENCES rag.document_versions ON DELETE CASCADE
);
CREATE INDEX chunks_fts ON rag.chunks USING gin (fts);
CREATE INDEX chunks_document ON rag.chunks (tenant_id, document_id, version);

-- ---------------------------------------------------------------- row-level security
-- FORCE makes the owner subject to the policies too (the owner otherwise bypasses RLS).
-- One policy per command: permissive policies are OR-ed, so keeping them separate avoids accidental widening.
ALTER TABLE rag.tenants           ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.tenants           FORCE  ROW LEVEL SECURITY;
ALTER TABLE rag.documents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.documents         FORCE  ROW LEVEL SECURITY;
ALTER TABLE rag.document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.document_versions FORCE  ROW LEVEL SECURITY;
ALTER TABLE rag.chunks            ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag.chunks            FORCE  ROW LEVEL SECURITY;

-- tenants: a caller can read only its own tenant row; tenant provisioning is not an application operation.
CREATE POLICY tenants_select ON rag.tenants FOR SELECT
  USING (tenant_id = rag.app_tenant());

-- documents: tenant AND document ACL to read, change or delete; tenant only to create.
CREATE POLICY documents_select ON rag.documents FOR SELECT
  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups());
CREATE POLICY documents_insert ON rag.documents FOR INSERT
  WITH CHECK (tenant_id = rag.app_tenant());
CREATE POLICY documents_update ON rag.documents FOR UPDATE
  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups())
  WITH CHECK (tenant_id = rag.app_tenant());
CREATE POLICY documents_delete ON rag.documents FOR DELETE
  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups());

-- versions inherit the document's visibility: the EXISTS subquery is itself subject to documents' policies.
CREATE POLICY versions_select ON rag.document_versions FOR SELECT
  USING (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.documents d
    WHERE d.tenant_id = document_versions.tenant_id AND d.document_id = document_versions.document_id));
CREATE POLICY versions_insert ON rag.document_versions FOR INSERT
  WITH CHECK (tenant_id = rag.app_tenant());
CREATE POLICY versions_update ON rag.document_versions FOR UPDATE
  USING (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.documents d
    WHERE d.tenant_id = document_versions.tenant_id AND d.document_id = document_versions.document_id))
  WITH CHECK (tenant_id = rag.app_tenant());
CREATE POLICY versions_delete ON rag.document_versions FOR DELETE
  USING (tenant_id = rag.app_tenant() AND EXISTS (
    SELECT 1 FROM rag.documents d
    WHERE d.tenant_id = document_versions.tenant_id AND d.document_id = document_versions.document_id));

-- chunks: tenant AND chunk ACL to read, change or delete; tenant only to create.
CREATE POLICY chunks_select ON rag.chunks FOR SELECT
  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups());
CREATE POLICY chunks_insert ON rag.chunks FOR INSERT
  WITH CHECK (tenant_id = rag.app_tenant());
CREATE POLICY chunks_update ON rag.chunks FOR UPDATE
  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups())
  WITH CHECK (tenant_id = rag.app_tenant());
CREATE POLICY chunks_delete ON rag.chunks FOR DELETE
  USING (tenant_id = rag.app_tenant() AND acl_groups && rag.app_groups());

-- ---------------------------------------------------------------- grants (least privilege)
GRANT SELECT ON rag.tenants TO rag_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON rag.documents, rag.document_versions, rag.chunks TO rag_app;
GRANT SELECT ON rag.schema_migrations TO rag_app;   -- readiness: is the schema at the expected version?
