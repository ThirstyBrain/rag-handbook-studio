"""Job queue, worker roles and handlers against real PostgreSQL."""

from __future__ import annotations

import hashlib
import io
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from pg import ScratchDb, requires_pg_roles, scratch_database
from pydantic import SecretStr
from worker_helpers import Rig

from rag_service.db.database import Database
from rag_service.db.identity import Identity
from rag_service.db.migrate import migrate
from rag_service.features.ingestion.storage import FilesystemObjectStore, raw_key
from rag_service.jobs.handlers import BadPayload, IntegrityError, ObjectMissing, make_handlers
from rag_service.jobs.queue import Job, JobQueue
from rag_service.jobs.worker import JobRunner

pytestmark = [pytest.mark.integration, requires_pg_roles]
REAL = Path(__file__).resolve().parents[2] / "database" / "migrations"


class Env:
    def __init__(self, db: ScratchDb) -> None:
        self.db = db
        self.admin = psycopg.connect(db.admin_url, autocommit=True)
        self.queue = JobQueue(SecretStr(db.worker_url), max_size=8)
        self.queue.open()
        self.rigs: list[Rig] = []

    def rig(self, objects: Path) -> Rig:
        rig = Rig(self.db, objects)
        self.rigs.append(rig)
        return rig

    def close(self) -> None:
        for rig in self.rigs:
            rig.close()
        self.queue.close()
        self.admin.close()

    def tenant(self) -> UUID:
        row = self.admin.execute(
            "INSERT INTO rag.tenants (name) VALUES (%s) RETURNING tenant_id", (f"t-{uuid4().hex}",)
        ).fetchone()
        assert row
        return row[0]  # type: ignore[no-any-return]

    def job(
        self,
        tenant: UUID,
        kind: str = "ingest_version",
        payload: str = "{}",
        max_attempts: int = 3,
        run_after: str = "now()",
        document: UUID | None = None,
    ) -> UUID:
        row = self.admin.execute(
            "INSERT INTO rag.ingestion_jobs (tenant_id, kind, payload, max_attempts, run_after, document_id) "  # noqa: S608
            f"VALUES (%s, %s, %s::jsonb, %s, {run_after}, %s) RETURNING job_id",
            (tenant, kind, payload, max_attempts, document),
        ).fetchone()
        assert row
        return row[0]  # type: ignore[no-any-return]

    def state(self, job_id: UUID) -> tuple[str, int, str | None]:
        row = self.admin.execute(
            "SELECT state, attempts, last_error FROM rag.ingestion_jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()
        assert row
        return row[0], row[1], row[2]


@pytest.fixture
def env() -> Iterator[Env]:
    with scratch_database() as db:
        migrate(db.owner_url, REAL)
        e = Env(db)
        try:
            yield e
        finally:
            e.close()


# ------------------------------------------------------------------ claiming


def test_concurrent_workers_never_claim_the_same_job(env: Env) -> None:
    t = env.tenant()
    created = {env.job(t) for _ in range(24)}
    claimed: list[UUID] = []
    lock = threading.Lock()

    def worker(name: str) -> None:
        while (job := env.queue.claim(name, 60)) is not None:
            with lock:
                claimed.append(job.job_id)

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(6)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert len(claimed) == len(created) == len(set(claimed)), "each job claimed exactly once"
    assert set(claimed) == created


def test_future_jobs_wait_and_oldest_runs_first(env: Env) -> None:
    t = env.tenant()
    later = env.job(t, run_after="now() + interval '1 hour'")
    old = env.job(t, run_after="now() - interval '2 minutes'")
    newer = env.job(t, run_after="now() - interval '1 minute'")
    first, second = env.queue.claim("w", 60), env.queue.claim("w", 60)
    assert first is not None and second is not None
    assert (first.job_id, second.job_id) == (old, newer)
    assert env.queue.claim("w", 60) is None, "a job scheduled for later must not be claimed yet"
    assert env.state(later)[0] == "queued"


# ------------------------------------------------------------------ outcomes, retries, leases


def test_success_clears_the_lease_and_only_the_holder_can_complete(env: Env) -> None:
    t = env.tenant()
    job_id = env.job(t)
    job = env.queue.claim("holder", 60)
    assert job is not None and job.attempts == 1
    assert env.queue.succeed(job, "someone-else") is False
    assert env.state(job_id)[0] == "running"
    assert env.queue.succeed(job, "holder") is True
    assert env.state(job_id) == ("succeeded", 1, None)
    assert env.queue.succeed(job, "holder") is False  # already finished


def test_failures_back_off_then_die_and_record_only_the_error_class(env: Env) -> None:
    t = env.tenant()

    class Boom(Exception):
        pass

    job_id = env.job(t, max_attempts=3)

    def handler(job: Job) -> None:
        raise Boom(f"SECRET-DATA {job.job_id} postgresql://u:pw@h/db")

    runner = JobRunner(
        env.queue,
        {"ingest_version": handler},
        worker_id="w",
        lease_s=60,
        backoff_base_s=60,
        backoff_cap_s=600,
    )
    assert runner.run_once() is True
    state, attempts, error = env.state(job_id)
    assert (state, attempts, error) == ("queued", 1, "Boom")
    wait = env.admin.execute(
        "SELECT run_after - now() FROM rag.ingestion_jobs WHERE job_id = %s", (job_id,)
    ).fetchone()
    assert wait is not None and wait[0].total_seconds() > 30, (
        "backoff must push run_after into the future"
    )
    assert runner.run_once() is False, "a job in backoff is not claimable"
    # make it due again twice more: attempts 2 and 3 -> dead
    for expected_state, expected_attempts in (("queued", 2), ("dead", 3)):
        env.admin.execute(
            "UPDATE rag.ingestion_jobs SET run_after = now() WHERE job_id = %s", (job_id,)
        )
        assert runner.run_once() is True
        assert env.state(job_id)[:2] == (expected_state, expected_attempts)
    dump = env.admin.execute("SELECT row_to_json(j)::text FROM rag.ingestion_jobs j").fetchone()
    assert dump is not None and "SECRET-DATA" not in dump[0] and "pw@h" not in dump[0]
    env.admin.execute(
        "UPDATE rag.ingestion_jobs SET run_after = now() WHERE job_id = %s", (job_id,)
    )
    assert runner.run_once() is False, "dead jobs are never claimed again"


def test_expired_lease_makes_a_crashed_workers_job_claimable_again(env: Env) -> None:
    t = env.tenant()
    job_id = env.job(t)
    crashed = env.queue.claim("crashed", 0.2)
    assert crashed is not None
    assert env.queue.claim("other", 60) is None, "lease still valid"
    time.sleep(0.5)
    taken = env.queue.claim("other", 60)
    assert taken is not None and taken.job_id == job_id and taken.attempts == 2
    assert env.queue.succeed(crashed, "crashed") is False, "the crashed worker lost its lease"
    assert env.queue.fail(crashed, "crashed", "Late", 0) is None
    assert env.queue.succeed(taken, "other") is True


def test_a_job_whose_lease_expires_after_its_last_attempt_is_marked_dead(env: Env) -> None:
    t = env.tenant()
    job_id = env.job(t, max_attempts=1)
    assert env.queue.claim("w", 0.2) is not None
    time.sleep(0.5)
    assert env.queue.claim("w2", 60) is None
    assert env.state(job_id) == ("dead", 2, "LeaseExpired")


def test_unknown_job_kind_fails_without_stalling_the_worker(env: Env) -> None:
    t = env.tenant()
    job_id = env.job(t)
    runner = JobRunner(env.queue, {}, worker_id="w", lease_s=60, backoff_base_s=0, backoff_cap_s=0)
    assert runner.run_once() is True
    assert env.state(job_id)[2] == "LookupError"


# ------------------------------------------------------------------ roles


def test_worker_role_has_only_its_narrow_privileges(env: Env) -> None:
    t = env.tenant()
    job_id = env.job(t)

    # 1. the privilege catalog. Table level: only chunks may be inserted into and deleted from, jobs
    # may be read and updated, nothing else at all.
    def privileges(table: str) -> dict[str, bool]:
        return {
            priv: bool(
                env.admin.execute(
                    "SELECT has_table_privilege('rag_worker', %s, %s)", (f"rag.{table}", priv)
                ).fetchone()[0]  # type: ignore[index]
            )
            for priv in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")
        }

    for table in ("documents", "document_versions", "tenants", "schema_migrations"):
        assert not any(privileges(table).values()), (
            f"rag_worker must have no table privilege on {table}"
        )
    assert privileges("chunks") == {
        "SELECT": False,
        "INSERT": True,
        "UPDATE": False,
        "DELETE": True,
        "TRUNCATE": False,
    }
    assert privileges("ingestion_jobs") == {
        "SELECT": True,
        "INSERT": False,
        "UPDATE": True,
        "DELETE": False,
        "TRUNCATE": False,
    }

    # column level: the worker reads ACL metadata and version state, never content, titles or hashes
    def column(table: str, name: str, priv: str) -> bool:
        return bool(
            env.admin.execute(
                "SELECT has_column_privilege('rag_worker', %s, %s, %s)",
                (f"rag.{table}", name, priv),
            ).fetchone()[0]  # type: ignore[index]
        )

    for table, name in (
        ("chunks", "content"),
        ("chunks", "section_path"),
        ("chunks", "acl_groups"),
        ("documents", "title"),
        ("documents", "source_id"),
        ("documents", "classification"),
        ("document_versions", "raw_object_uri"),
        ("document_versions", "content_sha256"),
    ):
        assert not column(table, name, "SELECT"), f"worker must not read {table}.{name}"
    assert column("documents", "acl_groups", "SELECT")
    assert column("document_versions", "state", "SELECT")
    assert {
        n
        for n in ("state", "extractor", "failure_reason")
        if column("document_versions", n, "UPDATE")
    } == {
        "state",
        "extractor",
        "failure_reason",
    }
    assert not column("document_versions", "content_sha256", "UPDATE")
    assert not column("documents", "acl_groups", "UPDATE")
    # 2. behaviour: with an identity set (so PostgreSQL can plan the query) every forbidden statement is refused
    with psycopg.connect(env.db.worker_url) as conn:
        assert conn.execute("SELECT count(*) FROM rag.ingestion_jobs").fetchone() == (1,)
        conn.commit()
        for sql in (
            "SELECT * FROM rag.documents",
            "SELECT title FROM rag.documents",
            "SELECT * FROM rag.document_versions",
            "SELECT * FROM rag.chunks",
            "SELECT content FROM rag.chunks",
            "SELECT * FROM rag.tenants",
            "UPDATE rag.chunks SET content = 'x'",
            "UPDATE rag.documents SET acl_groups = ARRAY['x']",
            "UPDATE rag.document_versions SET content_sha256 = repeat('a', 64)",
            "INSERT INTO rag.ingestion_jobs (tenant_id, kind) VALUES (gen_random_uuid(), 'ingest_version')",
            "DELETE FROM rag.ingestion_jobs",
            "CREATE TABLE rag.sneaky (id int)",
            "TRUNCATE rag.ingestion_jobs",
        ):
            conn.execute(
                "SELECT set_config('app.tenant_id', %s, true), set_config('app.groups', '[\"eng\"]', true)",
                (str(t),),
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)  # type: ignore[arg-type]
            conn.rollback()
        updated = conn.execute(
            "UPDATE rag.ingestion_jobs SET last_error = 'x' WHERE job_id = %s", (job_id,)
        ).rowcount
        assert updated == 1


def test_app_role_can_enqueue_and_read_only_its_own_tenants_jobs(env: Env) -> None:
    ta, tb = env.tenant(), env.tenant()
    job_b = env.job(tb)
    app = Database(
        SecretStr(env.db.app_url),
        min_size=1,
        max_size=2,
        acquire_timeout_s=10,
        statement_timeout_ms=30_000,
        idle_in_transaction_timeout_ms=15_000,
    )
    app.open()
    try:
        me = Identity(tenant_id=ta, user_id="u", groups=("eng",))
        own = app.run_sync(
            me,
            lambda c: c.execute(
                "INSERT INTO rag.ingestion_jobs (tenant_id, kind) VALUES (%s, 'ingest_version') RETURNING job_id",
                (ta,),
            ).fetchone(),
        )
        assert own is not None
        seen = app.run_sync(
            me, lambda c: {r["job_id"] for r in c.execute("SELECT job_id FROM rag.ingestion_jobs")}
        )
        assert seen == {own["job_id"]} and job_b not in seen
        for sql, params in (
            (
                "INSERT INTO rag.ingestion_jobs (tenant_id, kind) VALUES (%s, 'ingest_version')",
                (tb,),
            ),
            ("UPDATE rag.ingestion_jobs SET state = 'succeeded'", ()),
            ("DELETE FROM rag.ingestion_jobs", ()),
        ):
            with pytest.raises(psycopg.Error):
                app.run_sync(me, lambda c, s=sql, p=params: c.execute(s, p))  # type: ignore[misc,arg-type]
        assert env.state(job_b)[0] == "queued"
    finally:
        app.close()


# ------------------------------------------------------------------ handlers


def put(store: FilesystemObjectStore, tenant: UUID, doc: UUID, data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    key = raw_key(tenant, doc, sha)
    store.put(key, io.BytesIO(data), sha256=sha)
    return key, sha


def fake_job(tenant: UUID, kind: str, payload: dict[str, object], doc: UUID | None = None) -> Job:
    return Job(uuid4(), tenant, kind, doc, None, payload, 1, 3)


def test_ingest_handler_checks_presence_integrity_and_tenant_prefix(
    env: Env, tmp_path: Path
) -> None:
    rig = env.rig(tmp_path)
    store = rig.store
    handlers = make_handlers(store, env.queue, rig.pipeline)
    t, other, doc = env.tenant(), env.tenant(), uuid4()
    key, sha = put(store, t, doc, b"good bytes")
    with pytest.raises(IntegrityError):
        handlers["ingest_version"](
            fake_job(
                t, "ingest_version", {"key": key, "sha256": "0" * 64, "media_type": "text/plain"}
            )
        )
    missing = raw_key(t, doc, "b" * 64)
    with pytest.raises(ObjectMissing):
        handlers["ingest_version"](
            fake_job(
                t,
                "ingest_version",
                {"key": missing, "sha256": "b" * 64, "media_type": "text/plain"},
            )
        )
    with pytest.raises(BadPayload):  # a key under another tenant's prefix
        handlers["ingest_version"](
            fake_job(
                other, "ingest_version", {"key": key, "sha256": sha, "media_type": "text/plain"}
            )
        )
    for bad in ({}, {"key": "../etc/passwd", "sha256": sha}, {"key": key}):
        with pytest.raises(BadPayload):
            handlers["ingest_version"](fake_job(t, "ingest_version", bad))


def test_delete_handler_refuses_foreign_keys_and_removes_nothing_in_that_case(
    env: Env, tmp_path: Path
) -> None:
    rig = env.rig(tmp_path)
    store = rig.store
    handlers = make_handlers(store, env.queue, rig.pipeline)
    a, b, doc = env.tenant(), env.tenant(), uuid4()
    mine, _ = put(store, a, doc, b"mine")
    theirs, _ = put(store, b, doc, b"theirs")
    with pytest.raises(BadPayload):
        handlers["delete_objects"](fake_job(a, "delete_objects", {"keys": [mine, theirs]}, doc))
    assert store.exists(mine) and store.exists(theirs), "validation runs before any deletion"
    for bad in ({"keys": "not-a-list"}, {"keys": ["../x"]}, {}):
        with pytest.raises(BadPayload):
            handlers["delete_objects"](fake_job(a, "delete_objects", bad, doc))


def test_delete_handler_deletes_own_objects_and_cancels_queued_ingest_jobs(
    env: Env, tmp_path: Path
) -> None:
    rig = env.rig(tmp_path)
    store = rig.store
    handlers = make_handlers(store, env.queue, rig.pipeline)
    t, doc = env.tenant(), uuid4()
    k1, _ = put(store, t, doc, b"v1")
    k2, _ = put(store, t, doc, b"v2")
    pending = env.job(t, "ingest_version", document=doc)
    unrelated = env.job(t, "ingest_version", document=uuid4())
    handlers["delete_objects"](fake_job(t, "delete_objects", {"keys": [k1, k2]}, doc))
    assert not store.exists(k1) and not store.exists(k2)
    assert env.state(pending)[0] == "cancelled" and env.state(unrelated)[0] == "queued"
    handlers["delete_objects"](fake_job(t, "delete_objects", {"keys": [k1, k2]}, doc))  # idempotent
