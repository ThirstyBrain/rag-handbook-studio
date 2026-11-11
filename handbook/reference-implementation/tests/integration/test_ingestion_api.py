"""Ingestion API end to end against real PostgreSQL and a real (temporary) object store."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
from pg import ScratchDb, requires_pg_roles, scratch_database
from pydantic import SecretStr
from worker_helpers import Rig

from rag_service.core.config import Settings
from rag_service.db.migrate import migrate
from rag_service.jobs.handlers import make_handlers
from rag_service.jobs.queue import JobQueue
from rag_service.jobs.worker import JobRunner
from rag_service.main import create_app

pytestmark = [pytest.mark.integration, requires_pg_roles]
REAL = Path(__file__).resolve().parents[2] / "database" / "migrations"
TEXT = {"content-type": "text/plain"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class Env:
    client: httpx.AsyncClient
    db: ScratchDb
    objects: Path
    admin: psycopg.Connection
    closers: list[Callable[[], None]] = field(default_factory=list)

    def tenant(self) -> UUID:
        row = self.admin.execute(
            "INSERT INTO rag.tenants (name) VALUES (%s) RETURNING tenant_id", (f"t-{uuid4().hex}",)
        ).fetchone()
        assert row
        return row[0]  # type: ignore[no-any-return]

    def one(self, sql: str, *params: object) -> object:
        row = self.admin.execute(sql, params).fetchone()  # type: ignore[arg-type]
        return None if row is None else row[0]

    def object_files(self) -> list[Path]:
        return sorted(p for p in self.objects.rglob("*") if p.is_file())

    def runner(self) -> tuple[JobRunner, JobQueue]:
        queue = JobQueue(SecretStr(self.db.worker_url))
        queue.open()
        rig = Rig(self.db, self.objects)
        self.closers.append(rig.close)
        runner = JobRunner(
            queue,
            make_handlers(rig.store, queue, rig.pipeline),
            worker_id="test-worker",
            lease_s=30,
            backoff_base_s=0,
            backoff_cap_s=0,
        )
        return runner, queue


def headers(tenant: UUID, user: str = "u1", groups: str = "eng", **extra: str) -> dict[str, str]:
    return {"X-Dev-Tenant": str(tenant), "X-Dev-User": user, "X-Dev-Groups": groups, **extra}


@pytest.fixture
async def env(tmp_path: Path) -> AsyncIterator[Env]:
    with scratch_database() as db:
        migrate(db.owner_url, REAL)
        objects = tmp_path / "objects"
        app = create_app(
            Settings(  # type: ignore[call-arg]
                _env_file=None,
                environment="test",
                database_url=SecretStr(db.app_url),
                object_store_dir=objects,
                dev_identity_enabled=True,
                max_upload_bytes=4096,
                migrations_dir=REAL,
                db_pool_min_size=1,
                db_pool_max_size=6,
            ),
            configure_logs=False,
        )
        with psycopg.connect(db.admin_url, autocommit=True) as admin:
            async with app.router.lifespan_context(app):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
                    e = Env(client, db, objects, admin)
                    try:
                        yield e
                    finally:
                        for close in e.closers:
                            close()


async def upload(
    env: Env,
    tenant: UUID,
    data: bytes,
    *,
    source: str = "doc.txt",
    groups: str = "eng",
    ctype: str = "text/plain",
    **params: object,
) -> httpx.Response:
    return await env.client.post(
        "/v1/documents",
        params={"source_id": source, **params},  # type: ignore[arg-type]
        content=data,
        headers=headers(tenant, groups=groups, **{"content-type": ctype}),
    )


def jobs(env: Env, tenant: UUID, kind: str | None = None) -> int:
    sql = "SELECT count(*) FROM rag.ingestion_jobs WHERE tenant_id = %s"
    if kind:
        return int(env.one(sql + " AND kind = %s", tenant, kind))  # type: ignore[call-overload]
    return int(env.one(sql, tenant))  # type: ignore[call-overload]


# ------------------------------------------------------------------ happy path and idempotency


async def test_upload_creates_document_version_job_and_object(env: Env) -> None:
    t = env.tenant()
    data = b"Contractors are not covered by the leave policy."
    r = await upload(env, t, data, title="Leave policy")
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["version"] == 1 and body["state"] == "staged" and body["duplicate"] is False
    assert body["media_type"] == "text/plain" and body["size_bytes"] == len(data)
    doc = UUID(body["document_id"])
    files = env.object_files()
    assert [f.name for f in files] == [sha(data)] and files[0].read_bytes() == data
    assert files[0].parent.name == str(doc) and files[0].parent.parent.name == str(t)
    assert jobs(env, t, "ingest_version") == 1
    got = await env.client.get(f"/v1/documents/{doc}", headers=headers(t))
    assert got.status_code == 200 and got.json()["versions"][0]["job_state"] == "queued"


async def test_identical_upload_is_idempotent(env: Env) -> None:
    t = env.tenant()
    first = await upload(env, t, b"same content")
    second = await upload(env, t, b"same content")
    assert first.status_code == 202 and second.status_code == 200
    assert second.json()["duplicate"] is True and second.json()["version"] == 1
    assert second.json()["job_id"] is None
    assert jobs(env, t) == 1 and len(env.object_files()) == 1


async def test_new_content_creates_next_version_and_supersedes_the_unfinished_one(env: Env) -> None:
    t = env.tenant()
    doc = (await upload(env, t, b"version A")).json()["document_id"]
    r2 = await upload(env, t, b"version B")
    assert r2.status_code == 202 and r2.json()["version"] == 2
    versions = (await env.client.get(f"/v1/documents/{doc}", headers=headers(t))).json()["versions"]
    assert [(v["version"], v["state"]) for v in versions] == [(1, "superseded"), (2, "staged")]
    assert jobs(env, t, "ingest_version") == 2


async def test_reverting_to_earlier_content_creates_a_new_version(env: Env) -> None:
    t = env.tenant()
    await upload(env, t, b"A")
    await upload(env, t, b"B")
    r3 = await upload(env, t, b"A")  # A -> B -> A
    assert r3.status_code == 202 and r3.json()["version"] == 3 and r3.json()["duplicate"] is False


async def test_reverting_to_the_active_version_abandons_newer_staged_ones(env: Env) -> None:
    t = env.tenant()
    first = (await upload(env, t, b"A")).json()
    doc = first["document_id"]
    env.admin.execute(
        "UPDATE rag.document_versions SET state = 'active' WHERE document_id = %s AND version = 1",
        (doc,),
    )
    assert (await upload(env, t, b"B")).json()["version"] == 2  # staged next to the active one
    back = await upload(env, t, b"A")
    assert (
        back.status_code == 200 and back.json()["duplicate"] is True and back.json()["version"] == 1
    )
    versions = (await env.client.get(f"/v1/documents/{doc}", headers=headers(t))).json()["versions"]
    assert [(v["version"], v["state"]) for v in versions] == [(1, "active"), (2, "superseded")]


async def test_concurrent_identical_uploads_create_exactly_one_version(env: Env) -> None:
    t = env.tenant()
    results = await asyncio.gather(
        *(upload(env, t, b"race content", source="race.txt") for _ in range(5))
    )
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 200, 200, 200, 202], codes
    assert env.one("SELECT count(*) FROM rag.documents WHERE tenant_id = %s", t) == 1
    assert env.one("SELECT count(*) FROM rag.document_versions WHERE tenant_id = %s", t) == 1
    assert jobs(env, t) == 1
    assert len(env.object_files()) == 1, "objects stored for discarded plans must be removed"


# ------------------------------------------------------------------ access control


async def test_other_tenants_and_other_groups_cannot_see_or_delete_the_document(env: Env) -> None:
    ta, tb = env.tenant(), env.tenant()
    doc = (await upload(env, ta, b"secret", groups="hr", acl="hr")).json()["document_id"]
    for who in (headers(tb, groups="hr"), headers(ta, groups="eng")):
        assert (await env.client.get(f"/v1/documents/{doc}", headers=who)).status_code == 404
        assert (await env.client.delete(f"/v1/documents/{doc}", headers=who)).status_code == 404
    assert env.one("SELECT count(*) FROM rag.documents WHERE document_id = %s", doc) == 1
    listed = (await env.client.get("/v1/documents", headers=headers(tb, groups="hr"))).json()
    assert listed["items"] == []


async def test_acl_must_be_a_subset_of_the_callers_groups_and_non_empty(env: Env) -> None:
    t = env.tenant()
    r = await upload(env, t, b"x", groups="eng", acl="legal")
    assert r.status_code == 403 and r.json()["code"] == "acl_not_permitted"
    r = await upload(env, t, b"x", groups="")
    assert r.status_code == 422 and r.json()["code"] == "acl_required"
    ok = await upload(env, t, b"x", groups="eng,hr", acl="hr")
    assert ok.status_code == 202
    assert env.one(
        "SELECT acl_groups FROM rag.documents WHERE document_id = %s", ok.json()["document_id"]
    ) == ["hr"]
    assert env.one("SELECT count(*) FROM rag.documents WHERE tenant_id = %s", t) == 1


async def test_source_id_collision_with_an_invisible_document_is_a_conflict(env: Env) -> None:
    t = env.tenant()
    await upload(env, t, b"first", source="shared.txt", groups="hr", acl="hr")
    clash = await upload(env, t, b"other", source="shared.txt", groups="eng")
    assert clash.status_code == 409 and clash.json()["code"] == "document_conflict"
    assert env.one("SELECT count(*) FROM rag.documents WHERE tenant_id = %s", t) == 1
    assert len(env.object_files()) == 1, "the rejected upload must not leave an orphan object"


async def test_requests_without_valid_identity_are_rejected(env: Env) -> None:
    t = env.tenant()
    for h in (
        {},
        {"X-Dev-Tenant": str(t)},
        headers(t, user="bad user"),
        {**headers(t), "X-Dev-Tenant": "nope"},
    ):
        r = await env.client.post(
            "/v1/documents", params={"source_id": "a"}, content=b"x", headers=h
        )
        assert r.status_code == 401
    assert env.one("SELECT count(*) FROM rag.documents") == 0 and env.object_files() == []


# ------------------------------------------------------------------ content and size validation


async def test_content_validation(env: Env) -> None:
    t = env.tenant()
    pdf = await upload(env, t, b"%PDF-1.4 minimal", source="a.pdf", ctype="application/pdf")
    assert pdf.status_code == 202 and pdf.json()["media_type"] == "application/pdf"
    docx = await upload(
        env,
        t,
        b"PK\x03\x04docx-bytes",
        source="a.docx",
        ctype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert docx.status_code == 202
    for data, ctype in (
        (b"%PDF-1.4 minimal", "text/plain"),
        (b"plain text", "application/pdf"),
        (b"PK\x03\x04zip", "text/plain"),
        (b"bin\x00ary", "text/plain"),
        (b"\x7fELF", "application/octet-stream"),
        (b"text", "image/png"),
    ):
        r = await upload(env, t, data, source=f"bad-{uuid4().hex}", ctype=ctype)
        assert r.status_code == 415 and r.json()["code"] == "unsupported_media_type", (data, ctype)
    empty = await upload(env, t, b"", source="empty")
    assert empty.status_code == 422 and empty.json()["code"] == "empty_upload"
    assert env.one("SELECT count(*) FROM rag.documents WHERE tenant_id = %s", t) == 2
    assert len(env.object_files()) == 2


async def test_size_limit_is_enforced_on_the_stream_and_on_content_length(env: Env) -> None:
    t = env.tenant()

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(10):
            yield b"x" * 600  # 6,000 bytes with no Content-Length header (limit is 4,096)

    streamed = await env.client.post(
        "/v1/documents",
        params={"source_id": "big.txt"},
        content=chunks(),
        headers=headers(t, **TEXT),
    )
    assert streamed.status_code == 413 and streamed.json()["code"] == "payload_too_large"
    declared = await env.client.post(
        "/v1/documents",
        params={"source_id": "big2.txt"},
        content=b"x" * 100,
        headers=headers(t, **{"content-length": "999999"}, **TEXT),
    )
    assert declared.status_code in (400, 413)
    exact = await upload(env, t, b"y" * 4096, source="exact.txt")
    assert exact.status_code == 202
    assert env.one("SELECT count(*) FROM rag.documents WHERE tenant_id = %s", t) == 1
    assert len(env.object_files()) == 1, "rejected uploads must leave no object behind"


async def test_hostile_source_ids_are_data_not_paths(env: Env) -> None:
    t = env.tenant()
    for source in (
        "../../etc/passwd",
        "a/../../b",
        "C:\\windows\\system32",
        "x" * 1000,
        "name\nwith newline",
    ):
        r = await upload(env, t, f"content of {source[:5]}".encode(), source=source)
        assert r.status_code == 202, (source[:20], r.text)
    assert all(str(env.objects) in str(p.resolve()) for p in env.object_files())
    assert not (env.objects.parent / "etc").exists()
    for p in env.object_files():
        assert len(p.name) == 64 and p.relative_to(env.objects).parts[0] == "tenants"
    too_long = await upload(env, t, b"z", source="x" * 1001)
    assert too_long.status_code == 422


# ------------------------------------------------------------------ list and pagination


async def test_list_is_tenant_scoped_and_bounded(env: Env) -> None:
    ta, tb = env.tenant(), env.tenant()
    for i in range(3):
        await upload(env, ta, f"doc {i}".encode(), source=f"a{i}.txt")
    await upload(env, tb, b"other", source="b.txt")
    page = (await env.client.get("/v1/documents", params={"limit": 2}, headers=headers(ta))).json()
    assert len(page["items"]) == 2 and page["limit"] == 2
    rest = (
        await env.client.get("/v1/documents", params={"limit": 2, "offset": 2}, headers=headers(ta))
    ).json()
    assert len(rest["items"]) == 1
    sources = {i["source_id"] for i in page["items"] + rest["items"]}
    assert sources == {"a0.txt", "a1.txt", "a2.txt"}
    for bad in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 10_001}):
        assert (
            await env.client.get("/v1/documents", params=bad, headers=headers(ta))
        ).status_code == 422


# ------------------------------------------------------------------ deletion and erasure propagation


async def test_delete_removes_rows_immediately_and_objects_via_the_outbox(env: Env) -> None:
    t = env.tenant()
    doc = (await upload(env, t, b"to be erased")).json()["document_id"]
    await upload(env, t, b"second version of it")
    assert len(env.object_files()) == 2
    r = await env.client.delete(f"/v1/documents/{doc}", headers=headers(t))
    assert r.status_code == 204
    assert (await env.client.get(f"/v1/documents/{doc}", headers=headers(t))).status_code == 404
    for table in ("documents", "document_versions"):
        assert env.one(f"SELECT count(*) FROM rag.{table} WHERE document_id = %s", doc) == 0  # noqa: S608
    assert jobs(env, t, "delete_objects") == 1
    assert len(env.object_files()) == 2, "objects are removed by the worker, not inline"

    runner, queue = env.runner()
    try:
        while runner.run_once():
            pass
    finally:
        queue.close()
    assert env.object_files() == []
    states = {
        r[0]
        for r in env.admin.execute(
            "SELECT state FROM rag.ingestion_jobs WHERE tenant_id = %s", (t,)
        )
    }
    assert states <= {"succeeded", "cancelled"}, states


async def test_deleting_one_document_never_removes_another_documents_object(env: Env) -> None:
    t = env.tenant()
    same = b"identical bytes in two documents"
    d1 = (await upload(env, t, same, source="one.txt")).json()["document_id"]
    await upload(env, t, same, source="two.txt")
    assert len(env.object_files()) == 2, "objects are per document, never shared"
    await env.client.delete(f"/v1/documents/{d1}", headers=headers(t))
    runner, queue = env.runner()
    try:
        while runner.run_once():
            pass
    finally:
        queue.close()
    jobs = env.admin.execute(
        "SELECT kind, state, last_error FROM rag.ingestion_jobs ORDER BY created_at"
    ).fetchall()
    assert len(env.object_files()) == 1, jobs


async def test_worker_verifies_uploaded_objects(env: Env) -> None:
    t = env.tenant()
    doc = (await upload(env, t, b"verify me")).json()["document_id"]
    runner, queue = env.runner()
    try:
        assert runner.run_once() is True and runner.run_once() is False
    finally:
        queue.close()
    got = (await env.client.get(f"/v1/documents/{doc}", headers=headers(t))).json()
    assert got["versions"][0]["job_state"] == "succeeded"
