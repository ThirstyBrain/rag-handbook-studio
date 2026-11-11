"""Job queue operations for the worker, as the rag_worker role (ADR-015).

The worker role can read and update ``rag.ingestion_jobs`` and nothing else (no content tables). Claiming
uses FOR UPDATE SKIP LOCKED so concurrent workers never take the same job; a lease makes a crashed
worker's job claimable again; completion and failure only apply to the lease holder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import SecretStr

_CLAIM = """
WITH next AS (
  SELECT job_id FROM rag.ingestion_jobs
  WHERE (state = 'queued' AND run_after <= now())
     OR (state = 'running' AND lease_expires_at < now())
  ORDER BY run_after, created_at
  FOR UPDATE SKIP LOCKED
  LIMIT 1)
UPDATE rag.ingestion_jobs j
SET state = 'running', attempts = j.attempts + 1, locked_by = %(worker)s,
    lease_expires_at = now() + make_interval(secs => %(lease)s), updated_at = now()
FROM next
WHERE j.job_id = next.job_id
RETURNING j.job_id, j.tenant_id, j.kind, j.document_id, j.version, j.payload, j.attempts, j.max_attempts
"""


class PermanentFailure(Exception):
    """Raised by a handler when retrying cannot help (for example a file that cannot be parsed).
    ``reason`` is a short safe code; the job goes straight to ``dead``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Job:
    job_id: UUID
    tenant_id: UUID
    kind: str
    document_id: UUID | None
    version: int | None
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


def _job(row: dict[str, Any]) -> Job:
    return Job(**row)


class JobQueue:
    def __init__(self, dsn: SecretStr, *, min_size: int = 1, max_size: int = 4) -> None:
        self._pool: ConnectionPool[Any] = ConnectionPool(
            dsn.get_secret_value(),
            min_size=min_size,
            max_size=max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    def open(self) -> None:
        self._pool.open(wait=False)

    def close(self) -> None:
        self._pool.close()

    def claim(self, worker: str, lease_s: float) -> Job | None:
        """Claim the next runnable job. Jobs that already used all their attempts are marked dead."""
        while True:
            with self._pool.connection() as conn:
                row = conn.execute(_CLAIM, {"worker": worker, "lease": lease_s}).fetchone()
                if row is None:
                    return None
                job = _job(row)
                if job.attempts > job.max_attempts:  # lease expired after the last allowed attempt
                    conn.execute(
                        "UPDATE rag.ingestion_jobs SET state = 'dead', locked_by = NULL, "
                        "last_error = 'LeaseExpired', updated_at = now() WHERE job_id = %s",
                        (job.job_id,),
                    )
                    continue
                return job

    def succeed(self, job: Job, worker: str) -> bool:
        with self._pool.connection() as conn:
            updated: int = conn.execute(
                "UPDATE rag.ingestion_jobs SET state = 'succeeded', locked_by = NULL, "
                "lease_expires_at = NULL, last_error = NULL, updated_at = now() "
                "WHERE job_id = %s AND state = 'running' AND locked_by = %s",
                (job.job_id, worker),
            ).rowcount
            return updated == 1

    def fail(
        self, job: Job, worker: str, error_name: str, backoff_s: float, *, permanent: bool = False
    ) -> str | None:
        """Record a failure: retry later with backoff, or mark dead when attempts are used up or the
        failure is permanent."""
        with self._pool.connection() as conn:
            row = conn.execute(
                "UPDATE rag.ingestion_jobs SET "
                " state = CASE WHEN %s OR attempts >= max_attempts THEN 'dead' ELSE 'queued' END, "
                " run_after = now() + make_interval(secs => %s), locked_by = NULL, "
                " lease_expires_at = NULL, last_error = %s, updated_at = now() "
                "WHERE job_id = %s AND state = 'running' AND locked_by = %s RETURNING state",
                (permanent, backoff_s, error_name[:100], job.job_id, worker),
            ).fetchone()
            return None if row is None else str(row["state"])

    def cancel_pending(self, tenant_id: UUID, document_id: UUID) -> int:
        """Cancel queued ingest jobs of a deleted document."""
        with self._pool.connection() as conn:
            cancelled: int = conn.execute(
                "UPDATE rag.ingestion_jobs SET state = 'cancelled', updated_at = now() "
                "WHERE tenant_id = %s AND document_id = %s AND kind = 'ingest_version' "
                "AND state = 'queued'",
                (tenant_id, document_id),
            ).rowcount
            return cancelled
