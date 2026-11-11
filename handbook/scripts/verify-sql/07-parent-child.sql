-- Verifies handbook claims (Ch. 14): parent-child (small-to-big) retrieval in PostgreSQL.
-- Data: 200 documents x 5 sections x 6 chunks = 6,000 chunks; chunk vector = section centroid + small noise
-- (clustered, so neighbours tend to share a parent). 16-d synthetic vectors: shape of behaviour only.
DROP SCHEMA IF EXISTS v07 CASCADE;
CREATE SCHEMA v07;
SET search_path = v07, public;
SELECT setseed(0.42);

CREATE TABLE documents (doc_id int, version int, tenant text NOT NULL, PRIMARY KEY (doc_id, version));
CREATE TABLE sections (
  section_id int PRIMARY KEY, doc_id int NOT NULL, version int NOT NULL, title text NOT NULL,
  UNIQUE (section_id, doc_id, version),
  FOREIGN KEY (doc_id, version) REFERENCES documents ON DELETE CASCADE);
CREATE TABLE chunks (
  chunk_id int PRIMARY KEY, section_id int NOT NULL, doc_id int NOT NULL, version int NOT NULL,
  ordinal int NOT NULL, body text NOT NULL, acl text[] NOT NULL, e vector(16) NOT NULL,
  UNIQUE (section_id, ordinal),
  FOREIGN KEY (section_id, doc_id, version) REFERENCES sections (section_id, doc_id, version) ON DELETE CASCADE);
CREATE INDEX chunks_section ON chunks (section_id, ordinal);

INSERT INTO documents SELECT d, 1, CASE WHEN d % 2 = 0 THEN 'acme' ELSE 'globex' END FROM generate_series(1, 200) d;
INSERT INTO sections SELECT (d-1)*5 + s, d, 1, 'section ' || s FROM generate_series(1,200) d, generate_series(1,5) s;
CREATE TEMP TABLE centroids AS
  SELECT section_id, (SELECT array_agg(random()) FROM generate_series(1,16) g WHERE section_id IS NOT NULL) AS c FROM sections;
INSERT INTO chunks
SELECT (s.section_id-1)*6 + k, s.section_id, s.doc_id, s.version, k, 'chunk ' || k || ' of ' || s.section_id, ARRAY['all'],
       (SELECT array_agg(c.c[i] + 0.03*(random()-0.5)) FROM generate_series(1,16) i)::vector
FROM sections s JOIN centroids c USING (section_id), generate_series(1,6) k;
DO $$ BEGIN
  IF (SELECT count(DISTINCT e) FROM chunks) < 5990 THEN RAISE EXCEPTION 'harness bug: chunk vectors not distinct'; END IF;
  IF (SELECT count(DISTINCT section_id) FROM chunks) <> 1000 THEN RAISE EXCEPTION 'harness bug: section count'; END IF;
END $$;
CREATE INDEX chunks_hnsw ON chunks USING hnsw (e vector_l2_ops) WITH (m = 16, ef_construction = 64);
ANALYZE chunks;

-- T7a children collapse into few parents: distinct parent sections among the top-10 child hits, and the over-fetch needed
DO $$
DECLARE
  n_q int; q vector; distinct_sections int; sum_distinct int := 0; need int; sum_need int := 0; kk int;
BEGIN
  PERFORM set_config('enable_seqscan','off',true); PERFORM set_config('hnsw.ef_search','200',true);
  FOR n_q IN 1..40 LOOP
    q := (SELECT e FROM chunks WHERE chunk_id = 1 + (n_q*137) % 6000) ;
    q := (SELECT array_agg(x + 0.02*(random()-0.5)) FROM unnest(q::real[]) x)::vector;
    SELECT count(DISTINCT section_id) INTO distinct_sections FROM (SELECT section_id FROM chunks ORDER BY e <-> q LIMIT 10) s;
    sum_distinct := sum_distinct + distinct_sections;
    need := NULL;
    FOR kk IN 1..100 LOOP
      SELECT count(DISTINCT section_id) INTO distinct_sections FROM (SELECT section_id FROM chunks ORDER BY e <-> q LIMIT kk) s;
      IF distinct_sections >= 3 THEN need := kk; EXIT; END IF;
    END LOOP;
    sum_need := sum_need + coalesce(need, 100);
  END LOOP;
  RAISE NOTICE 'T7a avg distinct parent sections among top-10 child hits = % (of 10); avg child fetch needed for 3 distinct parents = %',
    round(sum_distinct/40.0, 2), round(sum_need/40.0, 1);
  IF sum_distinct/40.0 > 4 THEN RAISE EXCEPTION 'expected clustered children to collapse into few parents, got %', sum_distinct/40.0; END IF;
  IF sum_need/40.0 < 6 THEN RAISE EXCEPTION 'expected a materially larger child fetch for 3 distinct parents, got %', sum_need/40.0; END IF;
END $$;

-- T7b permission-safe expansion: a restricted sibling must not ride along with its parent
UPDATE chunks SET acl = ARRAY['hr'] WHERE section_id = 10 AND ordinal = 3;
DO $$
DECLARE naive int; safe int; leaked boolean;
BEGIN
  SELECT count(*) INTO naive FROM chunks WHERE section_id = 10;
  SELECT count(*) INTO safe  FROM chunks WHERE section_id = 10 AND acl && ARRAY['all'];
  SELECT bool_or(acl = ARRAY['hr']) INTO leaked FROM chunks WHERE section_id = 10;
  RAISE NOTICE 'T7b naive parent expansion returns % chunks (restricted sibling included: %); ACL-filtered expansion returns %', naive, leaked, safe;
  IF naive <> 6 OR safe <> 5 OR NOT leaked THEN RAISE EXCEPTION 'unexpected expansion counts naive=% safe=%', naive, safe; END IF;
END $$;

-- T7c deletion cascades through the hierarchy
DO $$
DECLARE before_c int; after_c int; after_s int;
BEGIN
  SELECT count(*) INTO before_c FROM chunks WHERE doc_id = 7;
  DELETE FROM documents WHERE doc_id = 7;
  SELECT count(*) INTO after_c FROM chunks WHERE doc_id = 7;
  SELECT count(*) INTO after_s FROM sections WHERE doc_id = 7;
  RAISE NOTICE 'T7c document 7: % chunks before delete, % chunks and % sections after', before_c, after_c, after_s;
  IF before_c <> 30 OR after_c <> 0 OR after_s <> 0 THEN RAISE EXCEPTION 'cascade did not remove the hierarchy'; END IF;
END $$;

-- T7d a child cannot point at a parent from a different document version
DO $$
DECLARE rejected boolean := false;
BEGIN
  INSERT INTO documents VALUES (1, 2, 'globex');           -- version 2 of document 1 exists, but has no sections yet
  BEGIN
    INSERT INTO chunks VALUES (999999, 1, 1, 2, 99, 'stale parent', ARRAY['all'], (SELECT array_agg(0.5) FROM generate_series(1,16))::vector);
  EXCEPTION WHEN foreign_key_violation THEN rejected := true; END;
  RAISE NOTICE 'T7d chunk (doc 1 v2) referencing section of doc 1 v1 rejected by composite FK: %', rejected;
  IF NOT rejected THEN RAISE EXCEPTION 'composite FK should reject a cross-version parent reference'; END IF;
END $$;
