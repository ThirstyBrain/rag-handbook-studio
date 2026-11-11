-- Verifies handbook claims (Ch. 5): HNSW recall vs ef_search, and filtered-search shortfall + iterative scan.
-- Data: 20,000 distinct 16-d uniform-random vectors; ~10% rows in tenant 'acme'. Synthetic, low-dimensional:
-- shape of the trade-off only; real embeddings (768-3072 d) behave differently.
DROP SCHEMA IF EXISTS v02 CASCADE;
CREATE SCHEMA v02;
SET search_path = v02, public;
SELECT setseed(0.42);

CREATE TABLE items (id int PRIMARY KEY, tenant text NOT NULL, e vector(16) NOT NULL);
INSERT INTO items
SELECT i, CASE WHEN random() < 0.10 THEN 'acme' ELSE 'other' END,
       (SELECT array_agg(random()) FROM generate_series(1, 16 + 0*i))::vector
FROM generate_series(1,20000) i;
DO $$ BEGIN IF (SELECT count(DISTINCT e) FROM items) < 19990 THEN RAISE EXCEPTION 'harness bug: vectors are not distinct'; END IF; END $$;
CREATE INDEX items_hnsw ON items USING hnsw (e vector_l2_ops) WITH (m = 16, ef_construction = 64);
ANALYZE items;

-- T2a recall@10 vs exact, by ef_search
DO $$
DECLARE
  ef_val int; n_q int; q vector; exact_ids int[]; got_ids int[]; h int; hits int; total int;
  efs int[] := ARRAY[10, 20, 40, 100, 200];
  qs vector[] := ARRAY[]::vector[];
  recalls numeric[] := ARRAY[]::numeric[]; rec numeric;
BEGIN
  FOR n_q IN 1..50 LOOP qs := qs || ((SELECT array_agg(random()) FROM generate_series(1,16))::vector); END LOOP;
  FOREACH ef_val IN ARRAY efs LOOP
    hits := 0; total := 0;
    FOR n_q IN 1..50 LOOP
      q := qs[n_q];
      PERFORM set_config('enable_indexscan','off',true); PERFORM set_config('enable_bitmapscan','off',true);
      SELECT array_agg(id) INTO exact_ids FROM (SELECT id FROM items ORDER BY e <-> q LIMIT 10) s;
      PERFORM set_config('enable_indexscan','on',true);  PERFORM set_config('enable_bitmapscan','on',true);
      PERFORM set_config('enable_seqscan','off',true);   PERFORM set_config('hnsw.ef_search', ef_val::text, true);
      SELECT array_agg(id) INTO got_ids FROM (SELECT id FROM items ORDER BY e <-> q LIMIT 10) s;
      PERFORM set_config('enable_seqscan','on',true);
      SELECT count(*) INTO h FROM unnest(got_ids) g WHERE g = ANY(exact_ids);
      hits := hits + h; total := total + 10;
    END LOOP;
    rec := round(hits::numeric/total, 3); recalls := recalls || rec;
    RAISE NOTICE 'T2a ef_search=% -> recall@10 = %', ef_val, rec;
  END LOOP;
  IF recalls[5] < 0.99 THEN RAISE EXCEPTION 'recall at ef_search=200 should be >= 0.99, got %', recalls[5]; END IF;
  IF recalls[1] >= recalls[5] THEN RAISE EXCEPTION 'recall should improve with ef_search'; END IF;
  FOR n_q IN 2..5 LOOP
    IF recalls[n_q] < recalls[n_q-1] - 0.015 THEN RAISE EXCEPTION 'recall dropped materially as ef_search rose'; END IF;
  END LOOP;
END $$;

-- T2b filter matching ~10% of rows, k=10: results returned
DO $$
DECLARE
  n_q int; q vector; c_default int; c_iter int; c_exact int;
  s_default int := 0; s_iter int := 0; s_exact int := 0; a_default numeric; a_iter numeric; a_exact numeric;
BEGIN
  FOR n_q IN 1..40 LOOP
    q := (SELECT array_agg(random()) FROM generate_series(1,16))::vector;
    PERFORM set_config('enable_seqscan','off',true);
    PERFORM set_config('hnsw.ef_search','40',true);
    PERFORM set_config('hnsw.iterative_scan','off',true);
    SELECT count(*) INTO c_default FROM (SELECT id FROM items WHERE tenant='acme' ORDER BY e <-> q LIMIT 10) s;
    PERFORM set_config('hnsw.iterative_scan','relaxed_order',true);
    SELECT count(*) INTO c_iter FROM (SELECT id FROM items WHERE tenant='acme' ORDER BY e <-> q LIMIT 10) s;
    PERFORM set_config('hnsw.iterative_scan','off',true);
    PERFORM set_config('enable_seqscan','on',true); PERFORM set_config('enable_indexscan','off',true); PERFORM set_config('enable_bitmapscan','off',true);
    SELECT count(*) INTO c_exact FROM (SELECT id FROM items WHERE tenant='acme' ORDER BY e <-> q LIMIT 10) s;
    PERFORM set_config('enable_indexscan','on',true); PERFORM set_config('enable_bitmapscan','on',true);
    s_default := s_default + c_default; s_iter := s_iter + c_iter; s_exact := s_exact + c_exact;
  END LOOP;
  a_default := round(s_default/40.0, 2); a_iter := round(s_iter/40.0, 2); a_exact := round(s_exact/40.0, 2);
  RAISE NOTICE 'T2b avg results of 10 requested: default (ef_search=40) = %, iterative_scan=relaxed_order = %, exact = %', a_default, a_iter, a_exact;
  IF a_default < 2.5 OR a_default > 5.5 THEN RAISE EXCEPTION 'post-filter shortfall expected near 4 of 10 (ef_search 40 x 10 percent), got %', a_default; END IF;
  IF a_iter < 9.9 THEN RAISE EXCEPTION 'iterative scan should return the full 10, got %', a_iter; END IF;
  IF a_exact <> 10 THEN RAISE EXCEPTION 'exact scan should return 10, got %', a_exact; END IF;
END $$;
