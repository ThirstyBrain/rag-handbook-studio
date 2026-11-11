"""Readiness orchestration. Business logic only: no HTTP, no database driver."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Literal, Protocol

from rag_service.core.events import READINESS_CHANGED, EventSink
from rag_service.features.health.schemas import (
    CheckResult,
    CheckStatus,
    ReadinessResponse,
)

_log = logging.getLogger(__name__)


class ReadinessCheck(Protocol):
    """A dependency probe. ``run`` returns normally when healthy and raises when not."""

    name: str

    async def run(self) -> None: ...


class HealthService:
    def __init__(
        self, checks: Sequence[ReadinessCheck], *, timeout_s: float, events: EventSink
    ) -> None:
        self._checks = list(checks)
        self._timeout_s = timeout_s
        self._events = events
        self._last_status: str | None = None

    async def _run_one(self, check: ReadinessCheck) -> tuple[str, CheckResult]:
        started = time.perf_counter()
        status, detail = CheckStatus.OK, None
        try:
            async with asyncio.timeout(self._timeout_s):
                await check.run()
        except TimeoutError:
            status, detail = CheckStatus.FAILED, "timeout"
        except Exception:
            # The exception may carry hostnames or credentials: no traceback, generic reason.
            _log.warning(
                "readiness_check_failed", extra={"ctx": {"check": check.name}}, exc_info=False
            )
            status, detail = CheckStatus.FAILED, "unavailable"
        latency = round((time.perf_counter() - started) * 1000, 2)
        return check.name, CheckResult(status=status, latency_ms=latency, detail=detail)

    async def readiness(self) -> ReadinessResponse:
        results = dict(await asyncio.gather(*(self._run_one(c) for c in self._checks)))
        overall: Literal["ok", "down"] = (
            "ok" if all(r.status is CheckStatus.OK for r in results.values()) else "down"
        )
        if overall != self._last_status:
            self._events.emit(READINESS_CHANGED, {"status": overall, "checks": len(results)})
            self._last_status = overall
        return ReadinessResponse(status=overall, checks=results)
