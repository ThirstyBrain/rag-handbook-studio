-- Verifies handbook claims (Ch. 3, Ch. 9): text-search tokenisation/stemming, ts_rank ignores collection statistics,
-- the hybrid_search SQL function (tenant + ACL inside both legs, weighted RRF), and the Chapter 3 schema.
DROP SCHEMA IF EXISTS v04 CASCADE;
CREATE SCHEMA v04;
SET search_path = v04, public;

-- T4a identifier tokenisation and stemming in the 'english' configuration
DO $$
DECLARE tv text; q text;
BEGIN
  tv := to_tsvector('english', 'Runbook: error E-4471 means the vector index is rebuilding.')::text;
  q  := websearch_to_tsquery('english', 'E-4471')::text;
  RAISE NOTICE 'T4a tsvector = %', tv;
  RAISE NOTICE 'T4a websearch_to_tsquery(E-4471) = %', q;
  IF tv NOT LIKE '%''-4471'':%' OR tv NOT LIKE '%''e'':%' THEN RAISE EXCEPTION 'expected E-4471 to be split into e and -4471, got %', tv; END IF;
  IF q <> '''e'' <-> ''-4471''' THEN RAISE EXCEPTION 'unexpected query form %', q; END IF;
  IF NOT (to_tsvector('english','Contractors are not covered') @@ websearch_to_tsquery('english','contractor')) THEN
    RAISE EXCEPTION 'english configuration should stem contractors -> contractor';
  END IF;
END $$;

-- T4b ts_rank / ts_rank_cd use no collection statistics: a rare and a common term score identically
CREATE TABLE hc (
  tenant_id uuid NOT NULL, chunk_id text NOT NULL, acl_groups text[] NOT NULL,
  content text NOT NULL, embedding vector(3) NOT NULL,
  fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  PRIMARY KEY (tenant_id, chunk_id));
CREATE INDEX hc_fts ON hc USING gin (fts);
CREATE INDEX hc_hnsw ON hc USING hnsw (embedding vector_ip_ops);
INSERT INTO hc (tenant_id, chunk_id, acl_groups, content, embedding) VALUES
 ('11111111-1111-1111-1111-111111111111','d1',ARRAY['all'],'ADR-017 rejected Kafka for the ingestion queue because of operational overhead.','[0.1,0.9,0.1]'),
 ('11111111-1111-1111-1111-111111111111','d2',ARRAY['all'],'Runbook: error E-4471 means the vector index is rebuilding. Wait for the rebuild to finish.','[0.1,0.1,0.9]'),
 ('11111111-1111-1111-1111-111111111111','d3',ARRAY['all'],'Parental leave policy: employees receive 16 weeks of paid leave.','[0.5,0.5,0.2]'),
 ('11111111-1111-1111-1111-111111111111','d4',ARRAY['all'],'Contractors are not covered by the parental leave policy unless their contract says otherwise.','[0.8,0.3,0.1]'),
 ('11111111-1111-1111-1111-111111111111','d5',ARRAY['all'],'The ingestion queue uses Azure Service Bus with dead-letter handling.','[0.2,0.8,0.2]'),
 ('11111111-1111-1111-1111-111111111111','d6',ARRAY['hr-admins'],'Executive compensation: contractors leave bonus bands.','[0.85,0.3,0.1]'),
 ('22222222-2222-2222-2222-222222222222','x1',ARRAY['all'],'Contractor leave contractor leave contractor leave policy for the other tenant.','[0.85,0.3,0.1]');
ANALYZE hc;
DO $$
DECLARE r_rare float4; r_common float4; cd_rare float4; cd_common float4;
BEGIN
  SELECT ts_rank(fts, to_tsquery('english','kafka')), ts_rank_cd(fts, to_tsquery('english','kafka')) INTO r_rare, cd_rare FROM hc WHERE chunk_id='d1';
  SELECT ts_rank(fts, to_tsquery('english','policy')), ts_rank_cd(fts, to_tsquery('english','policy')) INTO r_common, cd_common FROM hc WHERE chunk_id='d3';
  RAISE NOTICE 'T4b single occurrence: ts_rank rare=% common=%; ts_rank_cd rare=% common=%', r_rare, r_common, cd_rare, cd_common;
  IF r_rare <> r_common OR cd_rare <> cd_common THEN RAISE EXCEPTION 'expected identical scores (no collection statistics)'; END IF;
END $$;

-- T4c hybrid_search: tenant + ACL filters inside both legs; weighted RRF
CREATE OR REPLACE FUNCTION hybrid_search(
  p_tenant uuid, p_groups text[], q_text text, q_vec vector(3),
  cand int DEFAULT 50, n int DEFAULT 10,
  rrf_k int DEFAULT 60, w_lex float DEFAULT 1.0, w_vec float DEFAULT 1.0)
RETURNS TABLE (chunk_id text, score float) LANGUAGE sql STABLE AS $f$
  WITH lex AS (
    SELECT c.chunk_id,
           row_number() OVER (ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', q_text)) DESC) AS r
    FROM hc c
    WHERE c.tenant_id = p_tenant AND c.acl_groups && p_groups
      AND c.fts @@ websearch_to_tsquery('english', q_text)
    ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', q_text)) DESC
    LIMIT cand),
  vec AS (
    SELECT c.chunk_id,
           row_number() OVER (ORDER BY c.embedding <#> q_vec) AS r
    FROM hc c
    WHERE c.tenant_id = p_tenant AND c.acl_groups && p_groups
    ORDER BY c.embedding <#> q_vec
    LIMIT cand)
  SELECT chunk_id,
         COALESCE(w_lex / (rrf_k + lex.r), 0) + COALESCE(w_vec / (rrf_k + vec.r), 0) AS score
  FROM lex FULL OUTER JOIN vec USING (chunk_id)
  ORDER BY score DESC
  LIMIT n;
$f$;
DO $$
DECLARE ids text[]; top text; top_score float;
BEGIN
  SELECT array_agg(chunk_id ORDER BY score DESC) INTO ids
    FROM hybrid_search('11111111-1111-1111-1111-111111111111', ARRAY['all'], 'contractor leave', '[0.85,0.3,0.1]');
  top := ids[1];
  SELECT score INTO top_score FROM hybrid_search('11111111-1111-1111-1111-111111111111', ARRAY['all'], 'contractor leave', '[0.85,0.3,0.1]') ORDER BY score DESC LIMIT 1;
  IF 'x1' = ANY(ids) THEN RAISE EXCEPTION 'cross-tenant chunk x1 leaked'; END IF;
  IF 'd6' = ANY(ids) THEN RAISE EXCEPTION 'ACL-restricted chunk d6 leaked to a caller without hr-admins'; END IF;
  IF top <> 'd4' THEN RAISE EXCEPTION 'd4 should rank first (rank 1 in both legs), got %', top; END IF;
  IF abs(top_score - 2.0/61) > 1e-9 THEN RAISE EXCEPTION 'top RRF score should be 2/61, got %', top_score; END IF;
  SELECT array_agg(chunk_id) INTO ids
    FROM hybrid_search('11111111-1111-1111-1111-111111111111', ARRAY['all','hr-admins'], 'contractor leave', '[0.85,0.3,0.1]');
  IF NOT ('d6' = ANY(ids)) THEN RAISE EXCEPTION 'd6 should be visible with hr-admins'; END IF;
  RAISE NOTICE 'T4c hybrid_search OK: tenant/ACL filtered in both legs; d4 first with score 2/61 = %', top_score;
END $$;

-- T4d Chapter 3 schema. FINDING: a plain UNIQUE (tenant, document, content_sha256) blocks reverting to earlier content
-- (A -> B -> A). The corrected design allows at most one LIVE (staged or active) version per content hash.
CREATE TABLE documents (
  tenant_id       uuid        NOT NULL,
  document_id     uuid        NOT NULL DEFAULT gen_random_uuid(),
  source_id       text        NOT NULL,
  current_version int         NOT NULL,
  status          text        NOT NULL CHECK (status IN ('active','deleted')),
  acl_principals  text[]      NOT NULL DEFAULT '{}',
  PRIMARY KEY (tenant_id, document_id),
  UNIQUE (tenant_id, source_id)
);
-- original (flawed) design, kept only to demonstrate the flaw
CREATE TABLE document_versions_naive (
  tenant_id uuid NOT NULL, document_id uuid NOT NULL, version int NOT NULL, content_sha256 text NOT NULL,
  state text NOT NULL CHECK (state IN ('staged','active','superseded','failed')),
  PRIMARY KEY (tenant_id, document_id, version),
  UNIQUE (tenant_id, document_id, content_sha256)
);
-- corrected design
CREATE TABLE document_versions (
  tenant_id       uuid        NOT NULL,
  document_id     uuid        NOT NULL,
  version         int         NOT NULL,
  content_sha256  text        NOT NULL,
  raw_object_uri  text        NOT NULL,
  extractor       text        NOT NULL,
  state           text        NOT NULL CHECK (state IN ('staged','active','superseded','failed')),
  ingested_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, document_id, version)
);
CREATE UNIQUE INDEX document_versions_live_hash
  ON document_versions (tenant_id, document_id, content_sha256)
  WHERE state IN ('staged','active');
INSERT INTO documents (tenant_id, source_id, current_version, status)
VALUES ('11111111-1111-1111-1111-111111111111','hr/policy.md',1,'active');
DO $$
DECLARE d uuid; t uuid := '11111111-1111-1111-1111-111111111111'; n int;
BEGIN
  SELECT document_id INTO d FROM documents WHERE source_id='hr/policy.md';

  -- (1) the flaw: A -> B -> A is rejected by the original constraint
  INSERT INTO document_versions_naive VALUES (t, d, 1, 'A', 'active');
  UPDATE document_versions_naive SET state='superseded' WHERE version=1;
  INSERT INTO document_versions_naive VALUES (t, d, 2, 'B', 'active');
  UPDATE document_versions_naive SET state='superseded' WHERE version=2;
  BEGIN
    INSERT INTO document_versions_naive VALUES (t, d, 3, 'A', 'staged');
    RAISE EXCEPTION 'expected unique violation (the flaw): revert to earlier content should be blocked by the naive constraint';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'T4d FLAW CONFIRMED: plain UNIQUE blocks a revert A -> B -> A';
  END;

  -- (2) the fix: revert works because superseded versions are outside the partial unique index
  INSERT INTO document_versions VALUES (t, d, 1, 'A', 's3://raw/A', 'extractor@1', 'superseded', now());
  INSERT INTO document_versions VALUES (t, d, 2, 'B', 's3://raw/B', 'extractor@1', 'superseded', now());
  INSERT INTO document_versions VALUES (t, d, 3, 'A', 's3://raw/A', 'extractor@1', 'active', now());
  RAISE NOTICE 'T4d FIX OK: revert A -> B -> A accepted as version 3';

  -- (3) idempotency: re-ingesting the CURRENT content is still rejected / ignored
  BEGIN
    INSERT INTO document_versions VALUES (t, d, 4, 'A', 's3://raw/A', 'extractor@1', 'staged', now());
    RAISE EXCEPTION 'expected unique violation: same content as the live version must not create another version';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'T4d duplicate of the live content rejected';
  END;
  INSERT INTO document_versions VALUES (t, d, 4, 'A', 's3://raw/A', 'extractor@1', 'staged', now())
    ON CONFLICT (tenant_id, document_id, content_sha256) WHERE state IN ('staged','active') DO NOTHING;
  SELECT count(*) INTO n FROM document_versions WHERE document_id = d;
  IF n <> 3 THEN RAISE EXCEPTION 'ON CONFLICT DO NOTHING should leave exactly 3 versions, found %', n; END IF;

  -- (4) CHECK constraint
  BEGIN
    INSERT INTO document_versions VALUES (t, d, 5, 'C', 's3://raw/C', 'extractor@1', 'bogus', now());
    RAISE EXCEPTION 'expected check violation';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'T4d invalid state rejected by CHECK';
  END;
END $$;
