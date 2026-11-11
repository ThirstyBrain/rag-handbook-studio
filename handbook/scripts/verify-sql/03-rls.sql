-- Verifies handbook claims (Ch. 8, ADR-006): Postgres row-level security behaviour, pooled-connection identity
-- hazard, and RLS interaction with an HNSW index. Roles are cluster-global, so they are dropped/created here.
DROP SCHEMA IF EXISTS v03 CASCADE;
CREATE SCHEMA v03;
SET search_path = v03, public;
DROP ROLE IF EXISTS app_user;
DROP ROLE IF EXISTS owner_role;
CREATE ROLE owner_role NOLOGIN;
CREATE ROLE app_user NOLOGIN;            -- not owner, not superuser, no BYPASSRLS
GRANT USAGE ON SCHEMA v03 TO owner_role, app_user;
GRANT CREATE ON SCHEMA v03 TO owner_role;
SELECT setseed(0.7);

CREATE TABLE chunks (
  tenant_id uuid NOT NULL, chunk_id int NOT NULL, acl_groups text[] NOT NULL, e vector(16) NOT NULL,
  PRIMARY KEY (tenant_id, chunk_id));
INSERT INTO chunks
SELECT CASE WHEN r < 0.05 THEN '00000000-0000-0000-0000-000000000001'::uuid
            WHEN r < 0.50 THEN '00000000-0000-0000-0000-000000000002'::uuid
            ELSE '00000000-0000-0000-0000-000000000003'::uuid END,
       i, ARRAY[(ARRAY['eng','hr','legal'])[1 + floor(random()*3)::int]],
       (SELECT array_agg(random()) FROM generate_series(1, 16 + 0*i))::vector
FROM (SELECT i, random() AS r FROM generate_series(1,20000) i) s;
DO $$ BEGIN IF (SELECT count(DISTINCT e) FROM chunks) < 19990 THEN RAISE EXCEPTION 'harness bug: vectors are not distinct'; END IF; END $$;
CREATE INDEX chunks_hnsw ON chunks USING hnsw (e vector_l2_ops) WITH (m = 16, ef_construction = 64);
ALTER TABLE chunks OWNER TO owner_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON chunks TO app_user;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_acl ON chunks
  USING (tenant_id = current_setting('app.tenant_id')::uuid
         AND acl_groups && string_to_array(current_setting('app.groups'), ','));
ANALYZE chunks;

-- T3a/T3b superuser and table owner bypass RLS; FORCE RLS subjects the owner (fails closed with no identity set)
DO $$
DECLARE n_super bigint; n_owner bigint;
BEGIN
  SELECT count(*) INTO n_super FROM chunks;
  SET LOCAL ROLE owner_role;
  SELECT count(*) INTO n_owner FROM chunks;
  RESET ROLE;
  IF n_super <> 20000 OR n_owner <> 20000 THEN RAISE EXCEPTION 'superuser/owner should bypass RLS: % / %', n_super, n_owner; END IF;
  RAISE NOTICE 'T3a/b superuser sees %, owner (no FORCE) sees %', n_super, n_owner;
END $$;
ALTER TABLE chunks FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
  SET LOCAL ROLE owner_role;
  BEGIN
    PERFORM count(*) FROM chunks;
    RAISE EXCEPTION 'expected an error: FORCE RLS must subject the owner to the policy';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'expected an error%' THEN RAISE; END IF;
    RAISE NOTICE 'T3b owner with FORCE RLS and no identity -> error (fails closed): %', SQLERRM;
  END;
  RESET ROLE;
END $$;

-- T3c app role sees exactly what a direct WHERE predicts
DO $$
DECLARE n_app bigint; n_expected bigint;
BEGIN
  SELECT count(*) INTO n_expected FROM chunks
   WHERE tenant_id = '00000000-0000-0000-0000-000000000001' AND acl_groups && ARRAY['eng','hr'];
  SET LOCAL ROLE app_user;
  PERFORM set_config('app.tenant_id', '00000000-0000-0000-0000-000000000001', true);
  PERFORM set_config('app.groups', 'eng,hr', true);
  SELECT count(*) INTO n_app FROM chunks;
  RESET ROLE;
  IF n_app <> n_expected OR n_app = 0 THEN RAISE EXCEPTION 'RLS result % differs from direct predicate %', n_app, n_expected; END IF;
  RAISE NOTICE 'T3c app role sees % rows = direct predicate %', n_app, n_expected;
END $$;

-- T3d SET LOCAL identity disappears after the transaction -> next query fails closed
SET ROLE app_user;
BEGIN;
SELECT set_config('app.tenant_id', '00000000-0000-0000-0000-000000000002', true), set_config('app.groups', 'legal', true);
SELECT count(*) AS inside_txn FROM chunks;
COMMIT;
DO $$
BEGIN
  BEGIN
    PERFORM count(*) FROM chunks;
    RAISE EXCEPTION 'expected an error: identity must be gone after the transaction';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'expected an error%' THEN RAISE; END IF;
    RAISE NOTICE 'T3d after COMMIT the identity is gone -> query fails closed: %', SQLERRM;
  END;
END $$;
RESET ROLE;

-- T3e WITH CHECK defaults to USING: cross-tenant write rejected
DO $$
BEGIN
  SET LOCAL ROLE app_user;
  PERFORM set_config('app.tenant_id', '00000000-0000-0000-0000-000000000001', true);
  PERFORM set_config('app.groups', 'eng', true);
  BEGIN
    INSERT INTO chunks VALUES ('00000000-0000-0000-0000-000000000003', 999999, ARRAY['eng'],
                               (SELECT array_agg(0.5::real) FROM generate_series(1,16))::vector);
    RAISE EXCEPTION 'expected an error: cross-tenant insert must violate the policy';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'expected an error%' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%row-level security%' THEN RAISE EXCEPTION 'unexpected error: %', SQLERRM; END IF;
    RAISE NOTICE 'T3e cross-tenant INSERT rejected: %', SQLERRM;
  END;
  RESET ROLE;
END $$;

-- T3f row_security = off does not bypass; it errors when a policy would apply
DO $$
BEGIN
  SET LOCAL ROLE app_user;
  PERFORM set_config('row_security', 'off', true);
  BEGIN
    PERFORM count(*) FROM chunks;
    RAISE EXCEPTION 'expected an error with row_security = off';
  EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'expected an error%' THEN RAISE; END IF;
    IF SQLERRM NOT LIKE '%row-level security%' THEN RAISE EXCEPTION 'unexpected error: %', SQLERRM; END IF;
    RAISE NOTICE 'T3f row_security=off -> %', SQLERRM;
  END;
  RESET ROLE;
END $$;

-- T3g RLS + HNSW: tenant 1 holds ~5% of rows. RLS acts as a post-index FILTER, so default queries are starved.
DO $$
DECLARE n_q int; q vector; c_def int; c_it int; s_def int := 0; s_it int := 0; a_def numeric; a_it numeric;
        r text; plan text := '';
BEGIN
  SET LOCAL ROLE app_user;
  PERFORM set_config('app.tenant_id', '00000000-0000-0000-0000-000000000001', true);
  PERFORM set_config('app.groups', 'eng,hr,legal', true);
  PERFORM set_config('enable_seqscan', 'off', true);
  FOR n_q IN 1..40 LOOP
    q := (SELECT array_agg(random()) FROM generate_series(1,16))::vector;
    PERFORM set_config('hnsw.iterative_scan','off',true);
    SELECT count(*) INTO c_def FROM (SELECT chunk_id FROM chunks ORDER BY e <-> q LIMIT 10) s;
    PERFORM set_config('hnsw.iterative_scan','relaxed_order',true);
    SELECT count(*) INTO c_it FROM (SELECT chunk_id FROM chunks ORDER BY e <-> q LIMIT 10) s;
    s_def := s_def + c_def; s_it := s_it + c_it;
  END LOOP;
  a_def := round(s_def/40.0, 2); a_it := round(s_it/40.0, 2);
  FOR r IN EXECUTE $q$EXPLAIN (COSTS OFF) SELECT chunk_id FROM v03.chunks ORDER BY e <-> '[0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5]' LIMIT 10$q$ LOOP plan := plan || r || E'\n'; END LOOP;
  RESET ROLE;
  RAISE NOTICE 'T3g RLS on HNSW, tenant with ~5%% of rows: avg results of 10 = % (default) vs % (iterative_scan=relaxed_order)', a_def, a_it;
  IF a_def >= 5 THEN RAISE EXCEPTION 'expected starvation (< 5 of 10) for a ~5 percent tenant, got %', a_def; END IF;
  IF a_it < 9.9 THEN RAISE EXCEPTION 'iterative scan should restore 10 results, got %', a_it; END IF;
  IF plan NOT LIKE '%Index Scan using chunks_hnsw%' OR plan NOT LIKE '%Filter:%' THEN RAISE EXCEPTION 'expected RLS predicate as Filter on index scan: %', plan; END IF;
END $$;

-- T3h session-level (non-LOCAL) identity LEAKS into the next transaction on a pooled connection
DO $$
DECLARE first_n bigint; second_n bigint;
BEGIN
  SET LOCAL ROLE app_user;
  PERFORM set_config('app.tenant_id', '00000000-0000-0000-0000-000000000002', false);   -- false = session scope (the hazard)
  PERFORM set_config('app.groups', 'legal', false);
  SELECT count(*) INTO first_n FROM chunks;
  -- (in a real pool, the next request would run here without setting its own identity)
  SELECT count(*) INTO second_n FROM chunks;
  RESET ROLE;
  PERFORM set_config('app.tenant_id', '', false); PERFORM set_config('app.groups', '', false);
  IF first_n = 0 OR first_n <> second_n THEN RAISE EXCEPTION 'expected the leaked identity to persist: % vs %', first_n, second_n; END IF;
  RAISE NOTICE 'T3h with session-level SET, a request that never set an identity still saw % rows of another tenant', second_n;
END $$;
