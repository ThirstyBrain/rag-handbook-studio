"""Ingestion use cases. Every database access is one identity-scoped transaction (ADR-013).

Upload algorithm (idempotent, tenant-scoped):
  1. stream the body to a spooled file while hashing and enforcing the size cap; sniff the content type;
  2. look up the document for (tenant, source_id) to plan its id; store the raw object (content-addressed
     within the document) BEFORE committing database rows, so a job can never point at a missing object;
  3. one transaction: create/find the document; if a live version already has this content, return it
     (and abandon any newer staged versions); otherwise supersede older staged versions, create the next
     version as ``staged`` and enqueue an ``ingest_version`` job.
Deletion is one transaction that removes the rows and enqueues a ``delete_objects`` job (an outbox), so
object cleanup survives crashes and is retried by the worker.
"""

from __future__ import annotations

import asyncio
import hashlib
import tempfile
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import partial
from typing import Any, BinaryIO, cast
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from rag_service.core.errors import AppError
from rag_service.db.database import Conn, Database
from rag_service.db.identity import Identity
from rag_service.features.ingestion.media import HEAD_BYTES, detect_media_type
from rag_service.features.ingestion.schemas import (
    DocumentInfo,
    DocumentList,
    DocumentSummary,
    UploadResponse,
    VersionInfo,
)
from rag_service.features.ingestion.storage import ObjectStore, raw_key

_SPOOL_MEMORY = 1024 * 1024
_MAX_PLAN_RETRIES = 3


@dataclass(frozen=True)
class _Plan:
    document_id: UUID
    is_new: bool  # no document existed for this source id when we planned


class _Replan(Exception):
    """Another request created the document between planning and writing."""


class IngestionService:
    def __init__(
        self, db: Database, store: ObjectStore, *, max_upload_bytes: int, job_max_attempts: int
    ) -> None:
        self._db = db
        self._store = store
        self._max = max_upload_bytes
        self._attempts = job_max_attempts

    # ------------------------------------------------------------------ upload

    async def ingest(
        self,
        identity: Identity,
        *,
        source_id: str,
        title: str,
        acl: tuple[str, ...],
        declared_type: str | None,
        declared_length: int | None,
        body: AsyncIterator[bytes],
    ) -> UploadResponse:
        if not acl:
            raise AppError("acl_required", "At least one ACL group is required", 422)
        if not set(acl) <= set(identity.groups):
            raise AppError(
                "acl_not_permitted", "ACL may only name groups the caller belongs to", 403
            )
        if declared_length is not None and declared_length > self._max:
            raise AppError("payload_too_large", "Upload exceeds the size limit", 413)

        with tempfile.SpooledTemporaryFile(max_size=_SPOOL_MEMORY) as spool:
            digest = hashlib.sha256()
            head = bytearray()
            size = 0
            async for chunk in body:
                size += len(chunk)
                if size > self._max:  # enforced on the stream: Content-Length can lie or be absent
                    raise AppError("payload_too_large", "Upload exceeds the size limit", 413)
                if len(head) < HEAD_BYTES:
                    head += chunk[: HEAD_BYTES - len(head)]
                digest.update(chunk)
                spool.write(chunk)
            if size == 0:
                raise AppError("empty_upload", "The upload is empty", 422)
            media_type = detect_media_type(bytes(head), declared_type)
            if media_type is None:
                raise AppError(
                    "unsupported_media_type", "Content type is not allowed or does not match", 415
                )
            sha = digest.hexdigest()

            for _ in range(_MAX_PLAN_RETRIES):
                plan = await self._db.run(
                    identity, partial(self._plan, tenant=identity.tenant_id, source_id=source_id)
                )
                key = raw_key(identity.tenant_id, plan.document_id, sha)
                spool.seek(0)
                await asyncio.to_thread(self._store.put, key, cast(BinaryIO, spool), sha256=sha)
                write = partial(
                    self._write,
                    identity=identity,
                    plan=plan,
                    source_id=source_id,
                    title=title,
                    acl=acl,
                    sha=sha,
                    size=size,
                    media_type=media_type,
                    key=key,
                )
                try:
                    return await self._db.run(identity, write)
                except _Replan:
                    # Our object sits under a document id that is not the live one: remove it.
                    await asyncio.to_thread(self._store.delete, key)
                    continue
                except BaseException:
                    if plan.is_new:  # nothing references the object we just stored
                        await asyncio.to_thread(self._store.delete, key)
                    raise
        raise AppError("document_conflict", "Concurrent update, please retry", 409)

    @staticmethod
    def _plan(conn: Conn, tenant: UUID, source_id: str) -> _Plan:
        row = conn.execute(
            "SELECT document_id FROM rag.documents WHERE tenant_id = %s AND source_id = %s",
            (tenant, source_id),
        ).fetchone()
        return _Plan(row["document_id"], False) if row else _Plan(uuid4(), True)

    def _write(
        self,
        conn: Conn,
        identity: Identity,
        plan: _Plan,
        source_id: str,
        title: str,
        acl: tuple[str, ...],
        sha: str,
        size: int,
        media_type: str,
        key: str,
    ) -> UploadResponse:
        tenant = identity.tenant_id
        # FOR UPDATE serialises concurrent writers of the same document (so two identical uploads
        # cannot both create a version and trip the unique index).
        doc = conn.execute(
            "SELECT document_id FROM rag.documents WHERE tenant_id = %s AND source_id = %s FOR UPDATE",
            (tenant, source_id),
        ).fetchone()
        if doc is None:
            created = conn.execute(
                "INSERT INTO rag.documents (tenant_id, document_id, source_id, title, acl_groups) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (tenant_id, source_id) DO NOTHING "
                "RETURNING document_id",
                (tenant, plan.document_id, source_id, title, list(acl)),
            ).fetchone()
            if created is None:
                # Either a concurrent request created it (visible now: plan again) or it exists but is
                # not visible to this caller (ACL): report a conflict without revealing more.
                visible = conn.execute(
                    "SELECT 1 FROM rag.documents WHERE tenant_id = %s AND source_id = %s",
                    (tenant, source_id),
                ).fetchone()
                if visible is not None:
                    raise _Replan
                raise AppError("document_conflict", "A document with this source id exists", 409)
            doc_id: UUID = created["document_id"]
        else:
            doc_id = doc["document_id"]
            if doc_id != plan.document_id:
                raise _Replan
            conn.execute(
                "UPDATE rag.documents SET updated_at = now() WHERE tenant_id = %s AND document_id = %s",
                (tenant, doc_id),
            )

        versions = conn.execute(
            "SELECT version, content_sha256, state FROM rag.document_versions "
            "WHERE tenant_id = %s AND document_id = %s ORDER BY version DESC",
            (tenant, doc_id),
        ).fetchall()
        live = next(
            (
                v
                for v in versions
                if v["content_sha256"] == sha and v["state"] in ("staged", "active")
            ),
            None,
        )
        if live is not None:
            # Same content as a live version: nothing new to ingest. Newer staged versions are abandoned
            # because the latest intent is this content (a revert).
            conn.execute(
                "UPDATE rag.document_versions SET state = 'superseded' WHERE tenant_id = %s "
                "AND document_id = %s AND version > %s AND state = 'staged'",
                (tenant, doc_id, live["version"]),
            )
            return UploadResponse(
                document_id=doc_id,
                version=live["version"],
                state=live["state"],
                duplicate=True,
                job_id=None,
                media_type=media_type,
                size_bytes=size,
            )

        next_version = (versions[0]["version"] + 1) if versions else 1
        conn.execute(
            "UPDATE rag.document_versions SET state = 'superseded' WHERE tenant_id = %s "
            "AND document_id = %s AND state = 'staged'",
            (tenant, doc_id),
        )
        conn.execute(
            "INSERT INTO rag.document_versions "
            "(tenant_id, document_id, version, content_sha256, raw_object_uri, extractor, state) "
            "VALUES (%s, %s, %s, %s, %s, 'pending', 'staged')",
            (tenant, doc_id, next_version, sha, key),
        )
        job = conn.execute(
            "INSERT INTO rag.ingestion_jobs "
            "(tenant_id, kind, document_id, version, payload, max_attempts) "
            "VALUES (%s, 'ingest_version', %s, %s, %s, %s) RETURNING job_id",
            (
                tenant,
                doc_id,
                next_version,
                Jsonb({"key": key, "sha256": sha, "media_type": media_type, "size": size}),
                self._attempts,
            ),
        ).fetchone()
        assert job is not None
        return UploadResponse(
            document_id=doc_id,
            version=next_version,
            state="staged",
            duplicate=False,
            job_id=job["job_id"],
            media_type=media_type,
            size_bytes=size,
        )

    # ------------------------------------------------------------------ read

    async def get_document(self, identity: Identity, document_id: UUID) -> DocumentInfo:
        def work(conn: Conn) -> DocumentInfo | None:
            tenant = identity.tenant_id
            doc = conn.execute(
                "SELECT document_id, source_id, title, status, created_at FROM rag.documents "
                "WHERE tenant_id = %s AND document_id = %s",
                (tenant, document_id),
            ).fetchone()
            if doc is None:
                return None
            versions = conn.execute(
                "SELECT v.version, v.state, v.content_sha256, j.state AS job_state, j.attempts AS job_attempts "
                "FROM rag.document_versions v LEFT JOIN rag.ingestion_jobs j "
                "ON j.tenant_id = v.tenant_id AND j.document_id = v.document_id "
                "AND j.version = v.version AND j.kind = 'ingest_version' "
                "WHERE v.tenant_id = %s AND v.document_id = %s ORDER BY v.version",
                (tenant, document_id),
            ).fetchall()
            return DocumentInfo(**doc, versions=[VersionInfo(**v) for v in versions])

        info = await self._db.run(identity, work)
        if info is None:
            raise AppError("not_found", "Document not found", 404)
        return info

    async def list_documents(self, identity: Identity, limit: int, offset: int) -> DocumentList:
        def work(conn: Conn) -> list[dict[str, Any]]:
            return conn.execute(
                "SELECT document_id, source_id, title, status, created_at FROM rag.documents "
                "WHERE tenant_id = %s ORDER BY created_at DESC, document_id LIMIT %s OFFSET %s",
                (identity.tenant_id, limit, offset),
            ).fetchall()

        rows = await self._db.run(identity, work)
        return DocumentList(items=[DocumentSummary(**r) for r in rows], limit=limit, offset=offset)

    # ------------------------------------------------------------------ delete

    async def delete_document(self, identity: Identity, document_id: UUID) -> None:
        def work(conn: Conn) -> bool:
            tenant = identity.tenant_id
            doc = conn.execute(
                "SELECT document_id FROM rag.documents WHERE tenant_id = %s AND document_id = %s",
                (tenant, document_id),
            ).fetchone()
            if doc is None:
                return False
            shas = [
                r["content_sha256"]
                for r in conn.execute(
                    "SELECT DISTINCT content_sha256 FROM rag.document_versions "
                    "WHERE tenant_id = %s AND document_id = %s",
                    (tenant, document_id),
                )
            ]
            keys = [raw_key(tenant, document_id, sha) for sha in shas]
            deleted = conn.execute(
                "DELETE FROM rag.documents WHERE tenant_id = %s AND document_id = %s",
                (tenant, document_id),
            ).rowcount
            if deleted != 1:
                return False
            # Outbox: the same transaction records the object cleanup, so it cannot be lost.
            conn.execute(
                "INSERT INTO rag.ingestion_jobs (tenant_id, kind, document_id, payload, max_attempts) "
                "VALUES (%s, 'delete_objects', %s, %s, %s)",
                (tenant, document_id, Jsonb({"keys": keys}), self._attempts),
            )
            return True

        if not await self._db.run(identity, work):
            raise AppError("not_found", "Document not found", 404)
