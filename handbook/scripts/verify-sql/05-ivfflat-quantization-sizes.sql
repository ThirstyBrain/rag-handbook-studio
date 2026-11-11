-- Verifies handbook claims (Ch. 5): IVFFlat recall vs probes, probes = lists behaviour, binary quantization pattern,
-- half-precision index size. Data are synthetic (see per-test notes): shape of the trade-offs only.
DROP SCHEMA IF EXISTS v05 CASCADE;
CREATE SCHEMA v05;
SET search_path = v05, public;
SELECT setseed(0.11);

CREATE TABLE items (id int PRIMARY KEY, e vector(16) NOT NULL);
INSERT INTO items SELECT i, (SELECT array_agg(random()) FROM generate_series(1, 16 + 0*i))::vector FROM generate_series(1,20000) i;
DO $$ BEGIN IF (SELECT count(DISTINCT e) FROM items) < 19990 THEN RAISE EXCEPTION 'harness bug: vectors are not distinct'; END IF; END $$;
CREATE INDEX items_ivf ON items USING ivfflat (e vector_l2_ops) WITH (lists = 100);
ANALYZE items;

-- T5a IVFFlat lists=100: recall@10 vs probes
DO $$
DECLARE pr int; n_q int; q vector; exact_ids int[]; got_ids int[]; h int; hits int; total int;
        prs int[] := ARRAY[1, 3, 10, 30, 100];
        qs vector[] := ARRAY[]::vector[];
        recalls numeric[] := ARRAY[]::numeric[]; rec numeric; i int;
BEGIN
  FOR n_q IN 1..50 LOOP qs := qs || ((SELECT array_agg(random()) FROM generate_series(1,16))::vector); END LOOP;
  FOREACH pr IN ARRAY prs LOOP
    hits := 0; total := 0;
    FOR n_q IN 1..50 LOOP
      q := qs[n_q];
      PERFORM set_config('enable_indexscan','off',true); PERFORM set_config('enable_bitmapscan','off',true);
      SELECT array_agg(id) INTO exact_ids FROM (SELECT id FROM items ORDER BY e <-> q LIMIT 10) s;
      PERFORM set_config('enable_indexscan','on',true);  PERFORM set_config('enable_bitmapscan','on',true);
      PERFORM set_config('enable_seqscan','off',true);   PERFORM set_config('ivfflat.probes', pr::text, true);
      SELECT array_agg(id) INTO got_ids FROM (SELECT id FROM items ORDER BY e <-> q LIMIT 10) s;
      PERFORM set_config('enable_seqscan','on',true);
      SELECT count(*) INTO h FROM unnest(got_ids) g WHERE g = ANY(exact_ids);
      hits := hits + h; total := total + 10;
    END LOOP;
    rec := round(hits::numeric/total, 3); recalls := recalls || rec;
    RAISE NOTICE 'T5a IVFFlat lists=100 probes=% -> recall@10 = %', pr, rec;
  END LOOP;
  IF recalls[5] <> 1.000 THEN RAISE EXCEPTION 'probes = lists must give exact results (recall 1.0), got %', recalls[5]; END IF;
  IF recalls[4] < 0.95 THEN RAISE EXCEPTION 'probes=30 of 100 lists should reach >= 0.95, got %', recalls[4]; END IF;
  FOR i IN 2..5 LOOP
    IF recalls[i] < recalls[i-1] THEN RAISE EXCEPTION 'recall should not fall as probes rise'; END IF;
  END LOOP;
END $$;

-- T5a-plan  What the planner does at probes = lists (README says it will not use the index; record what 0.8.7 does)
DO $$
DECLARE r text; plan text := '';
BEGIN
  PERFORM set_config('ivfflat.probes', '100', true);
  FOR r IN EXECUTE $q$EXPLAIN (COSTS OFF) SELECT id FROM v05.items ORDER BY e <-> '[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5]' LIMIT 10$q$ LOOP plan := plan || r || ' | '; END LOOP;
  RAISE NOTICE 'T5a-plan probes=lists=100 plan: %', plan;
END $$;

-- T5b binary quantization + re-rank (README pattern) on mean-centred 16-d data. 16-bit codes are far too coarse to be
-- representative; this checks that the documented pattern runs and beats random, nothing more.
CREATE TABLE bq (id int PRIMARY KEY, e vector(16) NOT NULL);
INSERT INTO bq SELECT i, (SELECT array_agg(random() - 0.5) FROM generate_series(1, 16 + 0*i))::vector FROM generate_series(1,20000) i;
CREATE INDEX bq_hamming ON bq USING hnsw ((binary_quantize(e)::bit(16)) bit_hamming_ops);
ANALYZE bq;
DO $$
DECLARE n_q int; q vector; exact_ids int[]; got_ids int[]; h int; hits int := 0; total int := 0; rec numeric;
BEGIN
  FOR n_q IN 1..50 LOOP
    q := (SELECT array_agg(random() - 0.5) FROM generate_series(1,16))::vector;
    PERFORM set_config('enable_indexscan','off',true); PERFORM set_config('enable_bitmapscan','off',true);
    SELECT array_agg(id) INTO exact_ids FROM (SELECT id FROM bq ORDER BY e <=> q LIMIT 5) s;
    PERFORM set_config('enable_indexscan','on',true);  PERFORM set_config('enable_bitmapscan','on',true);
    PERFORM set_config('enable_seqscan','off',true);
    SELECT array_agg(id) INTO got_ids FROM (
      SELECT * FROM (SELECT id, e FROM bq ORDER BY binary_quantize(e)::bit(16) <~> binary_quantize(q) LIMIT 20) c
      ORDER BY e <=> q LIMIT 5) s;
    PERFORM set_config('enable_seqscan','on',true);
    SELECT count(*) INTO h FROM unnest(got_ids) g WHERE g = ANY(exact_ids);
    hits := hits + h; total := total + 5;
  END LOOP;
  rec := round(hits::numeric/total, 3);
  RAISE NOTICE 'T5b binary quantization (16-bit codes; Hamming top-20 then cosine re-rank to 5): recall@5 = %', rec;
  IF rec <= 0.05 THEN RAISE EXCEPTION 'pattern should beat random selection (>0.05), got %', rec; END IF;
END $$;

-- T5c measured index sizes at 1536 dimensions, 3000 rows
CREATE TABLE big (id int PRIMARY KEY, e vector(1536) NOT NULL);
INSERT INTO big SELECT i, (SELECT array_agg(random() - 0.5) FROM generate_series(1, 1536 + 0*i))::vector FROM generate_series(1,3000) i;
DO $$ BEGIN IF (SELECT count(DISTINCT e) FROM big) < 2990 THEN RAISE EXCEPTION 'harness bug: vectors are not distinct'; END IF; END $$;
CREATE INDEX big_vec  ON big USING hnsw (e vector_cosine_ops);
CREATE INDEX big_half ON big USING hnsw ((e::halfvec(1536)) halfvec_cosine_ops);
DO $$
DECLARE vec_b bigint; half_b bigint; raw_b bigint := 3000::bigint * (4*1536 + 8); ratio_half numeric; ratio_vec numeric;
BEGIN
  vec_b := pg_relation_size('v05.big_vec'); half_b := pg_relation_size('v05.big_half');
  ratio_half := round(half_b::numeric / vec_b, 3); ratio_vec := round(vec_b::numeric / raw_b, 3);
  RAISE NOTICE 'T5c HNSW(vector)=% bytes, HNSW(halfvec expr)=% bytes, raw vector data=% bytes; half/vector=%; vector index/raw=%',
               vec_b, half_b, raw_b, ratio_half, ratio_vec;
  IF ratio_half < 0.45 OR ratio_half > 0.55 THEN RAISE EXCEPTION 'halfvec expression index should be about half the size, ratio %', ratio_half; END IF;
  IF ratio_vec < 1.0 OR ratio_vec > 2.0 THEN RAISE EXCEPTION 'unexpected index/raw ratio %', ratio_vec; END IF;
END $$;
