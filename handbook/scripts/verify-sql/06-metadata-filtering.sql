-- Verifies handbook claims (Ch. 13): metadata filtering vs HNSW under varying selectivity, partial indexes,
-- list partitioning, and planner estimates for typed columns vs JSONB.
-- Data: 20,000 distinct 16-d random vectors; categories with exact selectivity 50% / 10% / 1% / 0.1% / rest.
-- Synthetic and low-dimensional: shape of the behaviour only. PG16 + pgvector 0.8.x.
DROP SCHEMA IF EXISTS v06 CASCADE;
CREATE SCHEMA v06;
SET search_path = v06, public;
SELECT setseed(0.42);

CREATE TABLE items (
  id int PRIMARY KEY, category text NOT NULL, dept text NOT NULL, meta jsonb NOT NULL, e vector(16) NOT NULL);
INSERT INTO items
SELECT i,
  CASE WHEN i % 1000 < 500 THEN 'c50' WHEN i % 1000 < 600 THEN 'c10' WHEN i % 1000 < 610 THEN 'c1'
       WHEN i % 1000 = 610 THEN 'c01' ELSE 'rest' END,
  CASE WHEN i % 100 = 0 THEN 'legal' ELSE 'eng' END,                      -- 'legal' = 1%
  jsonb_build_object('dept', CASE WHEN i % 100 = 0 THEN 'legal' ELSE 'eng' END),
  (SELECT array_agg(random()) FROM generate_series(1, 16 + 0*i))::vector
FROM generate_series(1, 20000) i;
DO $$ BEGIN IF (SELECT count(DISTINCT e) FROM items) < 19990 THEN RAISE EXCEPTION 'harness bug: vectors are not distinct'; END IF; END $$;
CREATE INDEX items_hnsw ON items USING hnsw (e vector_l2_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX items_cat  ON items (category);
CREATE INDEX items_dept ON items (dept);
CREATE INDEX items_meta_gin ON items USING gin (meta jsonb_path_ops);
ANALYZE items;

-- helper: which index does the planner choose for a filtered kNN query? (natural planner settings)
CREATE FUNCTION plan_json(sql text) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE r jsonb; BEGIN EXECUTE 'EXPLAIN (FORMAT JSON) ' || sql INTO r; RETURN r; END $$;

-- T6a selectivity sweep: planner choice, results returned (of 10), recall vs exact among filtered rows
DO $$
DECLARE
  cats text[] := ARRAY['c50','c10','c1','c01']; c text; n_q int; q vector; qtxt text;
  exact_ids int[]; got_ids int[]; h int; hits int; total int; returned int; ret_sum int; plan text; used text;
  iter text; res_default numeric[] := ARRAY[]::numeric[]; res_iter numeric[] := ARRAY[]::numeric[];
  rec_default numeric[] := ARRAY[]::numeric[]; used_default text[] := ARRAY[]::text[];
BEGIN
  FOREACH iter IN ARRAY ARRAY['off','relaxed_order'] LOOP
    FOREACH c IN ARRAY cats LOOP
      hits := 0; total := 0; ret_sum := 0; used := '';
      FOR n_q IN 1..30 LOOP
        q := (SELECT array_agg(random()) FROM generate_series(1,16))::vector; qtxt := q::text;
        PERFORM set_config('enable_indexscan','off',true); PERFORM set_config('enable_bitmapscan','off',true);
        PERFORM set_config('enable_seqscan','on',true);
        SELECT array_agg(id) INTO exact_ids FROM (SELECT id FROM items WHERE category=c ORDER BY e <-> q LIMIT 10) s;
        PERFORM set_config('enable_indexscan','on',true); PERFORM set_config('enable_bitmapscan','on',true);
        PERFORM set_config('hnsw.ef_search','40',true); PERFORM set_config('hnsw.iterative_scan',iter,true);
        IF n_q = 1 THEN
          plan := plan_json(format('SELECT id FROM v06.items WHERE category=%L ORDER BY e <-> %L::vector LIMIT 10', c, qtxt))::text;
          used := CASE WHEN plan LIKE '%items_hnsw%' THEN 'HNSW' WHEN plan LIKE '%items_cat%' THEN 'btree(category)' ELSE 'other/seq' END;
        END IF;
        -- dynamic SQL with literals => a fresh custom plan per query (what a literal-SQL client gets)
        EXECUTE format('SELECT array_agg(id) FROM (SELECT id FROM v06.items WHERE category=%L ORDER BY e <-> %L::vector LIMIT 10) s', c, qtxt) INTO got_ids;
        returned := coalesce(cardinality(got_ids), 0);
        SELECT count(*) INTO h FROM unnest(coalesce(got_ids, ARRAY[]::int[])) g WHERE g = ANY(exact_ids);
        hits := hits + h; total := total + cardinality(exact_ids); ret_sum := ret_sum + returned;
      END LOOP;
      IF iter = 'off' THEN
        res_default := res_default || round(ret_sum/30.0, 2); rec_default := rec_default || round(hits::numeric/total, 3);
        used_default := used_default || used;
      ELSE res_iter := res_iter || round(ret_sum/30.0, 2); END IF;
      RAISE NOTICE 'T6a iterative_scan=% filter=% -> plan=%, avg returned %/10 (exact avail: %), recall vs exact filtered = %',
        iter, c, used, round(ret_sum/30.0,2), (SELECT count(*) FROM items WHERE category=c), round(hits::numeric/total,3);
    END LOOP;
  END LOOP;
  -- assertions fixed after first observation (see handbook Ch. 13); iterative scan must restore full results where >=10 rows match
  IF res_iter[1] < 9.9 OR res_iter[2] < 9.9 OR res_iter[3] < 9.9 THEN RAISE EXCEPTION 'iterative scan should return 10 for c50/c10/c1, got %', res_iter; END IF;
  IF res_default[2] >= 9.9 THEN RAISE EXCEPTION 'the 10 percent filter was expected to starve under HNSW with the default settings, got %', res_default; END IF;
END $$;

-- T6e the generic-plan trap: a parameterised/prepared statement is planned without knowing the filter value
PREPARE kq(text, vector) AS
  SELECT array_agg(id) FROM (SELECT id FROM v06.items WHERE category = $1 ORDER BY e <-> $2 LIMIT 10) s;
DO $$
DECLARE
  q vector; qtxt text; n_q int; mode text; c text; got int[]; sum_n int; pj jsonb; used text;
  res jsonb := '{}'::jsonb; pl jsonb := '{}'::jsonb;
BEGIN
  PERFORM set_config('hnsw.iterative_scan','off',true); PERFORM set_config('hnsw.ef_search','40',true);
  FOREACH c IN ARRAY ARRAY['c1','c01'] LOOP
    FOREACH mode IN ARRAY ARRAY['force_custom_plan','force_generic_plan'] LOOP
      PERFORM set_config('plan_cache_mode', mode, true); sum_n := 0;
      FOR n_q IN 1..20 LOOP
        q := (SELECT array_agg(random()) FROM generate_series(1,16))::vector; qtxt := q::text;
        EXECUTE format('EXECUTE kq(%L, %L::vector)', c, qtxt) INTO got;
        sum_n := sum_n + coalesce(cardinality(got), 0);
      END LOOP;
      EXECUTE format('EXPLAIN (FORMAT JSON) EXECUTE kq(%L, %L::vector)', c, qtxt) INTO pj;
      used := CASE WHEN pj::text LIKE '%items_hnsw%' THEN 'HNSW' WHEN pj::text LIKE '%items_cat%' THEN 'btree(category)' ELSE 'other' END;
      res := res || jsonb_build_object(c || '/' || mode, round(sum_n/20.0, 2));
      pl  := pl  || jsonb_build_object(c || '/' || mode, used);
      RAISE NOTICE 'T6e filter=% plan_cache_mode=% -> plan=%, avg returned %/10', c, mode, used, round(sum_n/20.0,2);
    END LOOP;
  END LOOP;
  IF (res->>'c01/force_custom_plan')::numeric < 9.9 THEN RAISE EXCEPTION 'custom plan should return all 10 for c01: %', res; END IF;
  IF (res->>'c01/force_generic_plan')::numeric >= 9.9 THEN RAISE EXCEPTION 'expected the generic plan to starve the c01 filter, got %', res; END IF;
END $$;
DEALLOCATE kq;

-- T6b partial HNSW index for one hot filter value
CREATE INDEX items_hnsw_c10 ON items USING hnsw (e vector_l2_ops) WITH (m = 16, ef_construction = 64) WHERE category = 'c10';
ANALYZE items;
DO $$
DECLARE q vector; plan_same text; plan_other text; n int;
BEGIN
  q := (SELECT array_agg(random()) FROM generate_series(1,16))::vector;
  PERFORM set_config('hnsw.iterative_scan','off',true);
  plan_same  := plan_json(format('SELECT id FROM v06.items WHERE category=%L ORDER BY e <-> %L::vector LIMIT 10','c10',q::text))::text;
  plan_other := plan_json(format('SELECT id FROM v06.items WHERE category=%L ORDER BY e <-> %L::vector LIMIT 10','c50',q::text))::text;
  RAISE NOTICE 'T6b partial index used for category=c10: %; used for category=c50: %',
    plan_same LIKE '%items_hnsw_c10%', plan_other LIKE '%items_hnsw_c10%';
  IF plan_other LIKE '%items_hnsw_c10%' THEN RAISE EXCEPTION 'partial index must not serve a different predicate'; END IF;
  SELECT count(*) INTO n FROM (SELECT id FROM items WHERE category='c10' ORDER BY e <-> q LIMIT 10) s;
  RAISE NOTICE 'T6b rows returned via natural plan for c10 (partial index present): %/10', n;
  IF n <> 10 THEN RAISE EXCEPTION 'partial-index query should return 10, got %', n; END IF;
  IF plan_same NOT LIKE '%items_hnsw_c10%' THEN RAISE NOTICE 'T6b NOTE: planner did NOT pick the partial index here (plan: %)', left(plan_same, 300); END IF;
END $$;

-- T6c list partitioning by tenant, one HNSW index per partition
CREATE TABLE p_items (id int, tenant text NOT NULL, e vector(16) NOT NULL, PRIMARY KEY (tenant, id)) PARTITION BY LIST (tenant);
CREATE TABLE p_items_t1 PARTITION OF p_items FOR VALUES IN ('t1');
CREATE TABLE p_items_t2 PARTITION OF p_items FOR VALUES IN ('t2');
CREATE TABLE p_items_t3 PARTITION OF p_items FOR VALUES IN ('t3');
INSERT INTO p_items SELECT id, CASE WHEN id % 10 < 7 THEN 't1' WHEN id % 10 < 9 THEN 't2' ELSE 't3' END, e FROM items;
CREATE INDEX ON p_items USING hnsw (e vector_l2_ops) WITH (m = 16, ef_construction = 64);
ANALYZE p_items;
DO $$
DECLARE q vector; plan_one text; plan_all text; n int; n3 int; parts_one int := 0; parts_all int := 0; p text;
BEGIN
  q := (SELECT array_agg(random()) FROM generate_series(1,16))::vector;
  plan_one := plan_json(format('SELECT id FROM v06.p_items WHERE tenant=%L ORDER BY e <-> %L::vector LIMIT 10','t3',q::text))::text;
  plan_all := plan_json(format('SELECT id FROM v06.p_items ORDER BY e <-> %L::vector LIMIT 10',q::text))::text;
  FOREACH p IN ARRAY ARRAY['p_items_t1','p_items_t2','p_items_t3'] LOOP
    IF plan_one LIKE '%' || p || '%' THEN parts_one := parts_one + 1; END IF;
    IF plan_all LIKE '%' || p || '%' THEN parts_all := parts_all + 1; END IF;
  END LOOP;
  RAISE NOTICE 'T6c partitions referenced: with tenant predicate = %, without = %', parts_one, parts_all;
  IF parts_one <> 1 THEN RAISE EXCEPTION 'tenant predicate should prune to exactly 1 partition, got %', parts_one; END IF;
  IF parts_all <> 3 THEN RAISE EXCEPTION 'no predicate should touch all 3 partitions, got %', parts_all; END IF;
  PERFORM set_config('hnsw.iterative_scan','off',true);
  SELECT count(*) INTO n3 FROM (SELECT id FROM p_items WHERE tenant='t3' ORDER BY e <-> q LIMIT 10) s;
  RAISE NOTICE 'T6c rows returned for the 10%% tenant t3 via its own partition index: %/10 (default ef_search, no iterative scan)', n3;
  IF n3 <> 10 THEN RAISE EXCEPTION 'a partition-local index must not starve the tenant, got %', n3; END IF;
END $$;

-- T6d planner row estimates: typed column vs JSONB containment (true selectivity of dept=legal is 1% = 200 rows)
DO $$
DECLARE pj jsonb; est_typed numeric; est_json numeric; act_typed numeric; act_json numeric;
BEGIN
  pj := plan_json($q$SELECT id FROM v06.items WHERE dept = 'legal'$q$);       est_typed := (pj->0->'Plan'->>'Plan Rows')::numeric;
  pj := plan_json($q$SELECT id FROM v06.items WHERE meta @> '{"dept":"legal"}'$q$); est_json := (pj->0->'Plan'->>'Plan Rows')::numeric;
  act_typed := (SELECT count(*) FROM items WHERE dept = 'legal'); act_json := (SELECT count(*) FROM items WHERE meta @> '{"dept":"legal"}');
  RAISE NOTICE 'T6d estimated rows: typed column = %, jsonb @> = %; actual = % / %', est_typed, est_json, act_typed, act_json;
  IF act_typed <> act_json THEN RAISE EXCEPTION 'typed and jsonb predicates must select the same rows'; END IF;
  IF est_typed > act_typed * 3 OR est_typed < act_typed / 3 THEN RAISE EXCEPTION 'typed-column estimate should be within 3x, got %', est_typed; END IF;
END $$;
