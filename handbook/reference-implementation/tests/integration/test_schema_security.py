"""Tenant isolation, ACLs, privileges and integrity of the real schema, exercised as the restricted app role.

Seeding uses the superuser connection (it bypasses RLS); every assertion about visibility uses the
application role through the Database class, exactly as the service does.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from pg import ScratchDb, requires_pg_roles, scratch_database
from pydantic import SecretStr

from rag_service.db.database import Database
from rag_service.db.identity import Identity
from rag_service.db.migrate import migrate

pytestmark = [pytest.mark.integration, requires_pg_roles]
REAL = Path(__file__).resolve().parents[2] / "database" / "migrations"


# ------------------------------------------------------------------ fixtures and seeding helpers


@pytest.fixture(scope="module")
def pg() -> Iterator[ScratchDb]:
    with scratch_database() as db:
        migrate(db.owner_url, REAL)
        yield db


def make_db(pg: ScratchDb, *, size: int = 2, statement_timeout_ms: int = 30_000) -> Database:
    database = Database(
        SecretStr(pg.app_url),
        min_size=size,
        max_size=size,
        acquire_timeout_s=10,
        statement_timeout_ms=statement_timeout_ms,
        idle_in_transaction_timeout_ms=15_000,
    )
    database.open()
    return database


@pytest.fixture(scope="module")
def db(pg: ScratchDb) -> Iterator[Database]:
    database = make_db(pg)
    yield database
    database.close()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Seed:
    """Superuser-side data builder (bypasses RLS)."""

    def __init__(self, url: str) -> None:
        self.conn = psycopg.connect(url, autocommit=True)

    def tenant(self) -> UUID:
        row = self.conn.execute(
            "INSERT INTO rag.tenants (name) VALUES (%s) RETURNING tenant_id", (f"t-{uuid4().hex}",)
        ).fetchone()
        assert row
        return row[0]  # type: ignore[no-any-return]

    def document(
        self, tenant: UUID, acl: tuple[str, ...] = ("eng",), source: str | None = None
    ) -> UUID:
        row = self.conn.execute(
            "INSERT INTO rag.documents (tenant_id, source_id, acl_groups) VALUES (%s, %s, %s) "
            "RETURNING document_id",
            (tenant, source or f"s-{uuid4().hex}", list(acl)),
        ).fetchone()
        assert row
        return row[0]  # type: ignore[no-any-return]

    def version(
        self, tenant: UUID, doc: UUID, version: int = 1, content: str = "A", state: str = "active"
    ) -> None:
        self.conn.execute(
            "INSERT INTO rag.document_versions "
            "(tenant_id, document_id, version, content_sha256, raw_object_uri, extractor, state) "
            "VALUES (%s, %s, %s, %s, 's3://x', 'e@1', %s)",
            (tenant, doc, version, sha(content), state),
        )

    def chunk(
        self,
        tenant: UUID,
        doc: UUID,
        ordinal: int = 0,
        content: str = "hello world",
        acl: tuple[str, ...] = ("eng",),
        version: int = 1,
    ) -> UUID:
        row = self.conn.execute(
            "INSERT INTO rag.chunks (tenant_id, document_id, version, ordinal, content, acl_groups) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING chunk_id",
            (tenant, doc, version, ordinal, content, list(acl)),
        ).fetchone()
        assert row
        return row[0]  # type: ignore[no-any-return]

    def populated_tenant(
        self, acl: tuple[str, ...] = ("eng",), chunks: int = 3
    ) -> tuple[UUID, UUID, list[UUID]]:
        t = self.tenant()
        d = self.document(t, acl)
        self.version(t, d)
        return t, d, [self.chunk(t, d, i, f"chunk {i} of {d}", acl) for i in range(chunks)]


@pytest.fixture(scope="module")
def seed(pg: ScratchDb) -> Iterator[Seed]:
    s = Seed(pg.admin_url)
    yield s
    s.conn.close()


def ident(tenant: UUID, *groups: str) -> Identity:
    return Identity(tenant_id=tenant, user_id="user-1", groups=groups)


def count(conn: psycopg.Connection, table: str) -> int:
    row = conn.execute(f"SELECT count(*) AS n FROM rag.{table}").fetchone()  # noqa: S608 - fixed table names
    assert row
    return int(row["n"])  # type: ignore[call-overload]


# ------------------------------------------------------------------ roles and privileges


def test_app_role_is_not_privileged(seed: Seed) -> None:
    rows = seed.conn.execute(
        "SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole FROM pg_roles "
        "WHERE rolname IN ('rag_app', 'rag_owner')"
    ).fetchall()
    assert {r[0] for r in rows} == {"rag_app", "rag_owner"}
    assert all(not any(r[1:]) for r in rows), (
        "neither role may be superuser, BYPASSRLS, CREATEDB or CREATEROLE"
    )


def test_every_tenant_table_has_forced_rls_and_per_command_policies(seed: Seed) -> None:
    """Guard for FUTURE migrations: a new tenant-owned table without RLS fails this test."""
    tables = [
        r[0]
        for r in seed.conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid "
            "WHERE c.relnamespace = 'rag'::regnamespace AND c.relkind = 'r' AND a.attname = 'tenant_id' "
            "AND NOT a.attisdropped"
        )
    ]
    assert set(tables) >= {"tenants", "documents", "document_versions", "chunks"}
    for table in tables:
        flags = seed.conn.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = ('rag.' || %s)::regclass",
            (table,),
        ).fetchone()
        assert flags == (True, True), f"{table}: RLS must be enabled and forced"
        commands = {
            r[0]
            for r in seed.conn.execute(
                "SELECT cmd FROM pg_policies WHERE schemaname = 'rag' AND tablename = %s", (table,)
            )
        }
        assert commands & {"SELECT", "ALL"}, f"{table}: needs a SELECT-capable policy"
        # Tables where the application is deliberately limited (read-only tenants; jobs the API may only
        # enqueue and read; embeddings the worker only inserts and the app only reads, see test_embeddings_db) are exempt from the full CRUD set, but must still be forced-RLS and covered.
        if table not in {"tenants", "ingestion_jobs", "chunk_embeddings"}:
            assert {"SELECT", "INSERT", "UPDATE", "DELETE"} <= commands, f"{table}: needs all four"


def test_no_policy_applies_to_public(seed: Seed) -> None:
    """Guard: a policy without a TO clause applies to PUBLIC, so every role added later would inherit it
    (permissive policies are OR-ed). Found in migration 0001 while designing the worker's content path
    and fixed in 0003; this fails if a future migration repeats it."""
    rows = seed.conn.execute(
        "SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'rag' "
        "AND 'public' = ANY(roles) ORDER BY 1, 2"
    ).fetchall()
    assert rows == [], f"policies without a TO clause: {rows}"


def test_app_role_cannot_change_schema_or_policies_or_assume_owner(
    db: Database, seed: Seed
) -> None:
    t = seed.tenant()
    forbidden = [
        "CREATE TABLE rag.sneaky (id int)",
        "ALTER TABLE rag.chunks DISABLE ROW LEVEL SECURITY",
        "DROP TABLE rag.chunks",
        "ALTER TABLE rag.chunks NO FORCE ROW LEVEL SECURITY",
        "DROP POLICY chunks_select ON rag.chunks",
        "SET ROLE rag_owner",
        "INSERT INTO rag.tenants (name) VALUES ('evil')",
        "UPDATE rag.tenants SET name = 'x'",
        "DELETE FROM rag.schema_migrations",
        "TRUNCATE rag.chunks",
    ]
    for statement in forbidden:
        with pytest.raises(psycopg.Error):
            db.run_sync(ident(t, "eng"), lambda conn, s=statement: conn.execute(s))  # type: ignore[misc]


# ------------------------------------------------------------------ isolation


def test_reads_are_limited_to_the_callers_tenant(db: Database, seed: Seed) -> None:
    ta, _, chunks_a = seed.populated_tenant()
    tb, _, chunks_b = seed.populated_tenant(chunks=5)
    for tenant, expected in ((ta, set(chunks_a)), (tb, set(chunks_b))):
        seen = db.run_sync(
            ident(tenant, "eng"),
            lambda c: {r["chunk_id"] for r in c.execute("SELECT chunk_id FROM rag.chunks")},
        )
        assert seen == expected
    assert db.run_sync(ident(ta, "eng"), lambda c: count(c, "tenants")) == 1
    assert db.run_sync(ident(ta, "eng"), lambda c: count(c, "documents")) == 1
    assert db.run_sync(ident(ta, "eng"), lambda c: count(c, "document_versions")) == 1


def test_cross_tenant_writes_are_rejected_and_foreign_rows_are_untouchable(
    db: Database, seed: Seed
) -> None:
    ta, da, _ = seed.populated_tenant()
    tb, doc_b, chunks_b = seed.populated_tenant()
    me = ident(ta, "eng")

    def insert_as_other(conn: psycopg.Connection) -> None:
        conn.execute(
            "INSERT INTO rag.chunks (tenant_id, document_id, version, ordinal, content, acl_groups) "
            "VALUES (%s, %s, 1, 99, 'planted', %s)",
            (tb, doc_b, ["eng"]),
        )

    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="row-level security"):
        db.run_sync(me, insert_as_other)

    def move_own_row_to_other_tenant(conn: psycopg.Connection) -> None:
        conn.execute("UPDATE rag.documents SET tenant_id = %s WHERE document_id = %s", (tb, da))

    with pytest.raises(psycopg.Error):
        db.run_sync(me, move_own_row_to_other_tenant)

    def touch_foreign(conn: psycopg.Connection) -> tuple[int, int]:
        upd = conn.execute(
            "UPDATE rag.chunks SET content = 'pwned' WHERE chunk_id = %s", (chunks_b[0],)
        ).rowcount
        dele = conn.execute("DELETE FROM rag.chunks WHERE chunk_id = %s", (chunks_b[0],)).rowcount
        return upd, dele

    assert db.run_sync(me, touch_foreign) == (0, 0)
    row = seed.conn.execute(
        "SELECT content FROM rag.chunks WHERE chunk_id = %s", (chunks_b[0],)
    ).fetchone()
    assert row is not None and row[0] != "pwned"


def test_composite_foreign_keys_forbid_cross_tenant_references(seed: Seed) -> None:
    _, da, _ = seed.populated_tenant()
    tb = seed.tenant()
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        seed.conn.execute(
            "INSERT INTO rag.chunks (tenant_id, document_id, version, ordinal, content, acl_groups) "
            "VALUES (%s, %s, 1, 0, 'x', %s)",
            (tb, da, ["eng"]),
        )


def test_rls_with_check_blocks_moving_a_childless_row_to_another_tenant(
    db: Database, seed: Seed
) -> None:
    """Isolates the RLS WITH CHECK: with no child rows, no foreign key can mask a missing check."""
    ta = seed.tenant()
    tb = seed.tenant()
    doc = seed.document(ta)  # no versions, no chunks

    def move_with_where(conn: psycopg.Connection) -> None:
        conn.execute("UPDATE rag.documents SET tenant_id = %s WHERE document_id = %s", (tb, doc))

    def move_without_reading_columns(conn: psycopg.Connection) -> None:
        # No column is read, so PostgreSQL does not also apply the SELECT policy to the new row:
        # only the UPDATE policy's WITH CHECK stands between this statement and a cross-tenant move.
        conn.execute("UPDATE rag.documents SET tenant_id = %s", (tb,))

    for move in (move_with_where, move_without_reading_columns):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="row-level security"):
            db.run_sync(ident(ta, "eng"), move)
    assert seed.conn.execute(
        "SELECT tenant_id FROM rag.documents WHERE document_id = %s", (doc,)
    ).fetchone() == (ta,)


@pytest.mark.parametrize("table", ["tenants", "documents", "document_versions", "chunks"])
def test_each_table_fails_closed_on_its_own_when_no_identity_is_set(
    db: Database, table: str
) -> None:
    """Every table's policy must error without an identity, independent of the other tables' functions."""
    with pytest.raises(psycopg.Error), db._pool.connection() as conn:
        conn.execute(f"SELECT count(*) FROM rag.{table}")  # noqa: S608 - fixed table names


def test_tenant_policy_alone_fails_closed_when_only_groups_are_set(db: Database) -> None:
    """The tenants policy uses only app_tenant(); a NULL-returning variant would pass silently."""
    with pytest.raises(psycopg.Error), db._pool.connection() as conn:
        conn.execute("SELECT set_config('app.groups', '[\"eng\"]', true)")
        conn.execute("SELECT count(*) FROM rag.tenants")


def test_identity_settings_do_not_survive_the_transaction(pg: ScratchDb, seed: Seed) -> None:
    """Checks all three settings directly, so one leaking setting cannot hide behind another."""
    t = seed.tenant()
    single = make_db(pg, size=1)
    try:
        single.run_sync(Identity(tenant_id=t, user_id="leaky", groups=("eng",)), lambda c: None)
        with single._pool.connection() as conn:
            row = conn.execute(
                "SELECT current_setting('app.tenant_id', true) AS t, "
                "current_setting('app.user_id', true) AS u, current_setting('app.groups', true) AS g"
            ).fetchone()
        assert row == {"t": row["t"], "u": row["u"], "g": row["g"]} and all(
            v in (None, "") for v in row.values()
        ), f"identity leaked past the transaction: {row}"
    finally:
        single.close()


def test_missing_identity_fails_closed_instead_of_returning_nothing(db: Database) -> None:
    with pytest.raises(psycopg.Error), db._pool.connection() as conn:
        conn.execute("SELECT count(*) FROM rag.chunks")


def test_identity_cannot_leak_through_a_reused_pooled_connection(pg: ScratchDb, seed: Seed) -> None:
    """Pool of exactly one connection: request A's identity must not survive into request B."""
    ta, _, _ = seed.populated_tenant()
    single = make_db(pg, size=1)
    try:
        pid_a = single.run_sync(
            ident(ta, "eng"), lambda c: c.execute("SELECT pg_backend_pid() AS p").fetchone()
        )
        assert single.run_sync(ident(ta, "eng"), lambda c: count(c, "chunks")) > 0
        with (
            pytest.raises(psycopg.Error),
            single._pool.connection() as conn,
        ):  # next request: no identity
            assert conn.execute("SELECT pg_backend_pid() AS p").fetchone() == pid_a, (
                "same connection reused"
            )
            conn.execute("SELECT count(*) FROM rag.chunks")
    finally:
        single.close()


def test_row_security_off_does_not_bypass_policies(db: Database, seed: Seed) -> None:
    t, _, _ = seed.populated_tenant()

    def work(conn: psycopg.Connection) -> None:
        conn.execute("SET LOCAL row_security = off")
        conn.execute("SELECT count(*) FROM rag.chunks")

    with pytest.raises(psycopg.Error, match="row-level security"):
        db.run_sync(ident(t, "eng"), work)


# ------------------------------------------------------------------ ACLs


def test_chunk_acl_is_enforced_for_the_same_tenant(db: Database, seed: Seed) -> None:
    t = seed.tenant()
    d = seed.document(t, ("eng", "hr"))
    seed.version(t, d)
    eng = seed.chunk(t, d, 0, "engineering only", ("eng",))
    hr = seed.chunk(t, d, 1, "hr only", ("hr",))
    both = seed.chunk(t, d, 2, "shared", ("eng", "hr"))

    def visible(*groups: str) -> set[UUID]:
        return db.run_sync(
            ident(t, *groups),
            lambda c: {r["chunk_id"] for r in c.execute("SELECT chunk_id FROM rag.chunks")},
        )

    assert visible("eng") == {eng, both}
    assert visible("hr") == {hr, both}
    assert visible("eng", "hr") == {eng, hr, both}
    assert visible() == set() and visible("legal") == set()


def test_versions_inherit_the_documents_visibility(db: Database, seed: Seed) -> None:
    t = seed.tenant()
    d = seed.document(t, ("hr",))
    seed.version(t, d)
    assert db.run_sync(ident(t, "hr"), lambda c: count(c, "document_versions")) == 1
    assert db.run_sync(ident(t, "eng"), lambda c: count(c, "document_versions")) == 0
    assert db.run_sync(ident(t, "eng"), lambda c: count(c, "documents")) == 0


def test_empty_acl_is_rejected_by_constraint(seed: Seed) -> None:
    t = seed.tenant()
    with pytest.raises(psycopg.errors.CheckViolation):
        seed.document(t, ())
    d = seed.document(t, ("eng",))
    seed.version(t, d)
    with pytest.raises(psycopg.errors.CheckViolation):
        seed.chunk(t, d, 0, "x", ())


def test_writer_outside_the_acl_can_create_but_not_read_back(db: Database, seed: Seed) -> None:
    """Documented behaviour: INSERT needs only the tenant; RETURNING needs the SELECT policy too."""
    t = seed.tenant()
    me = ident(t, "eng")

    def create(conn: psycopg.Connection) -> None:
        conn.execute(
            "INSERT INTO rag.documents (tenant_id, source_id, acl_groups) VALUES (%s, 'doc', %s)",
            (t, ["hr"]),
        )

    db.run_sync(me, create)  # allowed
    assert db.run_sync(me, lambda c: count(c, "documents")) == 0  # but not visible to this caller
    with pytest.raises(psycopg.Error):
        db.run_sync(
            me,
            lambda c: c.execute(
                "INSERT INTO rag.documents (tenant_id, source_id, acl_groups) VALUES (%s, 'doc2', %s) RETURNING document_id",
                (t, ["hr"]),
            ),
        )


# ------------------------------------------------------------------ lifecycle, integrity, search


def test_deleting_a_document_cascades_to_versions_and_chunks(db: Database, seed: Seed) -> None:
    t, d, _ = seed.populated_tenant()
    deleted = db.run_sync(
        ident(t, "eng"),
        lambda c: c.execute("DELETE FROM rag.documents WHERE document_id = %s", (d,)).rowcount,
    )
    assert deleted == 1
    for table in ("document_versions", "chunks"):
        row = seed.conn.execute(
            f"SELECT count(*) FROM rag.{table} WHERE document_id = %s",  # noqa: S608 - fixed table names
            (d,),
        ).fetchone()
        assert row == (0,), f"{table} rows must be gone after the document is deleted"


def test_revert_allowed_but_duplicate_of_live_content_rejected(seed: Seed) -> None:
    t = seed.tenant()
    d = seed.document(t)
    seed.version(t, d, 1, "A", "superseded")
    seed.version(t, d, 2, "B", "superseded")
    seed.version(t, d, 3, "A", "active")  # revert A -> B -> A
    with pytest.raises(psycopg.errors.UniqueViolation):
        seed.version(t, d, 4, "A", "staged")  # same content as the live version


def test_full_text_column_is_generated_and_tenant_scoped(db: Database, seed: Seed) -> None:
    t1, d1, _ = seed.populated_tenant(chunks=0)
    seed.chunk(t1, d1, 0, "Contractors are not covered by the leave policy")
    t2, d2, _ = seed.populated_tenant(chunks=0)
    seed.chunk(t2, d2, 0, "Contractor leave rules for the other tenant")

    def search(conn: psycopg.Connection) -> list[str]:
        rows = conn.execute(
            "SELECT content FROM rag.chunks WHERE fts @@ websearch_to_tsquery('english', 'contractor')"
        ).fetchall()
        return [r["content"] for r in rows]

    assert db.run_sync(ident(t1, "eng"), search) == [
        "Contractors are not covered by the leave policy"
    ]


# ------------------------------------------------------------------ the Database class itself


def test_transaction_rolls_back_on_error_and_commits_on_success(db: Database, seed: Seed) -> None:
    t = seed.tenant()
    me = ident(t, "eng")

    def create_then_fail(conn: psycopg.Connection) -> None:
        conn.execute(
            "INSERT INTO rag.documents (tenant_id, source_id, acl_groups) VALUES (%s, 'x', %s)",
            (t, ["eng"]),
        )
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        db.run_sync(me, create_then_fail)
    assert seed.conn.execute(
        "SELECT count(*) FROM rag.documents WHERE tenant_id = %s", (t,)
    ).fetchone() == (0,)

    db.run_sync(
        me,
        lambda c: c.execute(
            "INSERT INTO rag.documents (tenant_id, source_id, acl_groups) VALUES (%s, 'y', %s)",
            (t, ["eng"]),
        ),
    )
    assert seed.conn.execute(
        "SELECT count(*) FROM rag.documents WHERE tenant_id = %s", (t,)
    ).fetchone() == (1,)


async def test_async_run_executes_in_a_worker_thread(db: Database, seed: Seed) -> None:
    t, _, chunks = seed.populated_tenant()
    n = await db.run(ident(t, "eng"), lambda c: count(c, "chunks"))
    assert n == len(chunks)


def test_statement_timeout_is_applied(pg: ScratchDb, seed: Seed) -> None:
    quick = make_db(pg, size=1, statement_timeout_ms=200)
    t = seed.tenant()
    try:
        with pytest.raises(psycopg.errors.QueryCanceled):
            quick.run_sync(ident(t, "eng"), lambda c: c.execute("SELECT pg_sleep(2)"))
    finally:
        quick.close()
