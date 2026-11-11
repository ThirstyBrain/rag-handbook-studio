-- Verifies handbook claims (Ch. 2, Ch. 5): operator semantics, storage sizes, dimension limits,
-- operator-class matching. Assertions RAISE EXCEPTION on failure (psql runs with ON_ERROR_STOP).
DROP SCHEMA IF EXISTS v01 CASCADE;
CREATE SCHEMA v01;
SET search_path = v01, public;
SELECT setseed(0.42);

-- T1a  <#> is NEGATIVE inner product; <=> cosine distance; <-> L2
DO $$
DECLARE a vector := '[1,2,0.5,0]'; b vector := '[2,4,1,0]'; ip float8; cd float8; l2 float8;
BEGIN
  ip := (a <#> b); cd := (a <=> b); l2 := (a <-> b);
  RAISE NOTICE 'T1a a<#>b=% (inner product %), a<=>b=%, a<->b=%', ip, -ip, cd, l2;
  IF abs(ip - (-(1*2 + 2*4 + 0.5*1))) > 1e-9 THEN RAISE EXCEPTION '<#> is not the negative inner product'; END IF;
  IF abs(cd) > 1e-6 THEN RAISE EXCEPTION 'same direction must have cosine distance 0, got %', cd; END IF;
  IF abs(l2 - sqrt(1 + 4 + 0.25)) > 1e-5 THEN RAISE EXCEPTION 'L2 mismatch'; END IF;
END $$;

-- T1b  vector = 4*d + 8 bytes, halfvec = 2*d + 8 bytes
DO $$
DECLARE v int; h int;
BEGIN
  SELECT pg_column_size(array_fill(0.1::real, ARRAY[1536])::vector) INTO v;
  SELECT pg_column_size(array_fill(0.1::real, ARRAY[1536])::vector::halfvec) INTO h;
  RAISE NOTICE 'T1b vector(1536)=% bytes, halfvec(1536)=% bytes', v, h;
  IF v <> 4*1536 + 8 THEN RAISE EXCEPTION 'vector size formula wrong: %', v; END IF;
  IF h <> 2*1536 + 8 THEN RAISE EXCEPTION 'halfvec size formula wrong: %', h; END IF;
END $$;

-- T1c  HNSW index dimension limits: vector <= 2000, halfvec <= 4000
CREATE TABLE d1536 (id int, e vector(1536));
CREATE INDEX ON d1536 USING hnsw (e vector_cosine_ops);
CREATE TABLE d2000 (id int, e vector(2000));
CREATE INDEX ON d2000 USING hnsw (e vector_cosine_ops);
CREATE TABLE d3072 (id int, e vector(3072));
CREATE TABLE h3072 (id int, e halfvec(3072));
CREATE INDEX ON h3072 USING hnsw (e halfvec_cosine_ops);
CREATE TABLE d3072x (id int, e vector(3072));
CREATE INDEX d3072_halfvec_expr ON d3072x USING hnsw ((e::halfvec(3072)) halfvec_cosine_ops);
DO $$
BEGIN
  BEGIN
    EXECUTE 'CREATE INDEX ON v01.d3072 USING hnsw (e vector_cosine_ops)';
    RAISE EXCEPTION 'expected failure: vector(3072) must not be HNSW-indexable';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'expected failure%' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%more than 2000 dimensions%' THEN RAISE EXCEPTION 'unexpected error: %', SQLERRM; END IF;
    RAISE NOTICE 'T1c vector(3072) HNSW index rejected: %', SQLERRM;
  END;
  BEGIN
    EXECUTE 'CREATE TABLE v01.h4001 (id int, e halfvec(4001))';
    EXECUTE 'CREATE INDEX ON v01.h4001 USING hnsw (e halfvec_cosine_ops)';
    RAISE EXCEPTION 'expected failure: halfvec(4001) must not be HNSW-indexable';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'expected failure%' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%more than 4000 dimensions%' THEN RAISE EXCEPTION 'unexpected error: %', SQLERRM; END IF;
    RAISE NOTICE 'T1c halfvec(4001) HNSW index rejected: %', SQLERRM;
  END;
END $$;

-- T1d  an <=> query cannot use an index built with vector_ip_ops; <#> can
CREATE TABLE oc (id int, e vector(8));
INSERT INTO oc SELECT i, (SELECT array_agg(random()) FROM generate_series(1, 8 + 0*i))::vector FROM generate_series(1,3000) i;
DO $$ BEGIN IF (SELECT count(DISTINCT e) FROM oc) < 2990 THEN RAISE EXCEPTION 'harness bug: vectors are not distinct'; END IF; END $$;
CREATE INDEX oc_ip ON oc USING hnsw (e vector_ip_ops);
ANALYZE oc;
DO $$
DECLARE r text; plan_ip text := ''; plan_cos text := '';
BEGIN
  PERFORM set_config('enable_seqscan', 'off', true);
  FOR r IN EXECUTE $q$EXPLAIN (COSTS OFF) SELECT id FROM v01.oc ORDER BY e <#> '[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5]' LIMIT 5$q$ LOOP plan_ip := plan_ip || r || E'\n'; END LOOP;
  FOR r IN EXECUTE $q$EXPLAIN (COSTS OFF) SELECT id FROM v01.oc ORDER BY e <=> '[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5]' LIMIT 5$q$ LOOP plan_cos := plan_cos || r || E'\n'; END LOOP;
  IF plan_ip NOT LIKE '%Index Scan using oc_ip%' THEN RAISE EXCEPTION 'matching operator class should use the index: %', plan_ip; END IF;
  IF plan_cos LIKE '%Index Scan using oc_ip%' THEN RAISE EXCEPTION 'non-matching operator must NOT use the ip index: %', plan_cos; END IF;
  RAISE NOTICE 'T1d <#> uses oc_ip; <=> falls back to Seq Scan + Sort even with enable_seqscan=off';
END $$;

-- T1e  documented defaults (touch an index first so the pgvector GUCs are registered)
SELECT count(*) FROM (SELECT 1 FROM oc ORDER BY e <#> '[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5]' LIMIT 1) s;
DO $$
BEGIN
  IF current_setting('hnsw.ef_search') <> '40' THEN RAISE EXCEPTION 'hnsw.ef_search default is %', current_setting('hnsw.ef_search'); END IF;
  IF current_setting('hnsw.iterative_scan') <> 'off' THEN RAISE EXCEPTION 'hnsw.iterative_scan default is %', current_setting('hnsw.iterative_scan'); END IF;
  IF current_setting('hnsw.max_scan_tuples') <> '20000' THEN RAISE EXCEPTION 'hnsw.max_scan_tuples default is %', current_setting('hnsw.max_scan_tuples'); END IF;
  IF current_setting('ivfflat.probes') <> '1' THEN RAISE EXCEPTION 'ivfflat.probes default is %', current_setting('ivfflat.probes'); END IF;
  RAISE NOTICE 'T1e defaults match README: ef_search=40, iterative_scan=off, max_scan_tuples=20000, probes=1';
END $$;
