"""Job handlers. A handler raises on failure; the runner records only the exception class name.

Handlers run as the worker role. It has a narrow write path to the chunks of staged versions of the job's
tenant (ADR-016) and cannot read stored content; raw bytes come from the object store.
"""

from __future__ import annotations

from collections.abc import Callable

from rag_service.features.ingestion.pipeline import IngestPipeline
from rag_service.features.ingestion.storage import (
    ObjectStore,
    StorageError,
    tenant_prefix,
    validate_key,
)
from rag_service.jobs.queue import Job, JobQueue

Handler = Callable[[Job], None]


class ObjectMissing(Exception):
    pass


class IntegrityError(Exception):
    pass


class BadPayload(Exception):
    pass


def make_handlers(
    store: ObjectStore, queue: JobQueue, pipeline: IngestPipeline
) -> dict[str, Handler]:
    def ingest_version(job: Job) -> None:
        """Verify the raw object (tenant prefix, presence, hash), then extract, chunk and store it."""
        try:
            key = validate_key(str(job.payload["key"]))
            expected = str(job.payload["sha256"])
            media_type = str(job.payload["media_type"])
        except (KeyError, StorageError):
            raise BadPayload from None
        if not key.startswith(tenant_prefix(job.tenant_id)):
            raise BadPayload
        if not store.exists(key):
            raise ObjectMissing
        if store.sha256(key) != expected:
            raise IntegrityError
        pipeline.process(job, key, media_type)

    def delete_objects(job: Job) -> None:
        """Delete a deleted document's raw objects, then cancel its queued ingest jobs."""
        keys = job.payload.get("keys")
        if not isinstance(keys, list):
            raise BadPayload
        prefix = tenant_prefix(job.tenant_id)
        for raw in keys:
            try:
                key = validate_key(str(raw))
            except StorageError:
                raise BadPayload from None
            if not key.startswith(
                prefix
            ):  # a crafted payload must never reach another tenant's objects
                raise BadPayload
        for raw in keys:
            store.delete(str(raw))
        if job.document_id is not None:
            queue.cancel_pending(job.tenant_id, job.document_id)

    return {"ingest_version": ingest_version, "delete_objects": delete_objects}
