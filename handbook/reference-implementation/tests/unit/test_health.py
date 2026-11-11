"""Unit tests: liveness/readiness behaviour with fake dependency checks."""

from __future__ import annotations

import asyncio
import time

from rag_service.core.events import APP_STARTED, READINESS_CHANGED
from rag_service.features.health.service import HealthService
from tests_types import ClientFor, MakeApp


class Ok:
    name = "ok_dep"

    async def run(self) -> None:
        return None


class Fails:
    name = "bad_dep"

    async def run(self) -> None:
        raise ConnectionError(
            "could not connect to postgresql://user:hunter2@internal-host:5432/db"
        )


class Hangs:
    name = "slow_dep"

    async def run(self) -> None:
        await asyncio.sleep(30)


async def test_live_never_checks_dependencies(make_app: MakeApp, client_for: ClientFor) -> None:
    r = await client_for(make_app(checks=[Fails()])).get("/health/live")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_ready_with_no_checks_is_ok(make_app: MakeApp, client_for: ClientFor) -> None:
    r = await client_for(make_app()).get("/health/ready")
    assert r.status_code == 200 and r.json() == {"status": "ok", "checks": {}}


async def test_ready_ok_with_healthy_check(make_app: MakeApp, client_for: ClientFor) -> None:
    r = await client_for(make_app(checks=[Ok()])).get("/health/ready")
    assert r.status_code == 200 and r.json()["checks"]["ok_dep"]["status"] == "ok"


async def test_failing_check_gives_503_without_leaking_details(
    make_app: MakeApp, client_for: ClientFor
) -> None:
    r = await client_for(make_app(checks=[Ok(), Fails()])).get("/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "down"
    assert r.json()["checks"]["bad_dep"] == {
        "status": "failed",
        "latency_ms": r.json()["checks"]["bad_dep"]["latency_ms"],
        "detail": "unavailable",
    }
    assert r.json()["checks"]["ok_dep"]["status"] == "ok"
    assert "hunter2" not in r.text and "internal-host" not in r.text


async def test_hanging_check_times_out_without_blocking_others(
    make_app: MakeApp, client_for: ClientFor
) -> None:
    started = time.perf_counter()
    r = await client_for(make_app(checks=[Ok(), Hangs()], readiness_check_timeout_s=0.2)).get(
        "/health/ready"
    )
    assert time.perf_counter() - started < 2
    assert r.status_code == 503 and r.json()["checks"]["slow_dep"]["detail"] == "timeout"
    assert r.json()["checks"]["ok_dep"]["status"] == "ok"


async def test_status_change_emits_one_event_per_transition(sink) -> None:  # type: ignore[no-untyped-def]
    flaky = Ok()
    service = HealthService([flaky], timeout_s=1, events=sink)
    await service.readiness()
    await service.readiness()
    flaky.run = Fails().run  # type: ignore[method-assign]
    await service.readiness()
    changes = [props["status"] for name, props in sink.events if name == READINESS_CHANGED]
    assert changes == ["ok", "down"]


async def test_lifespan_emits_app_started(make_app: MakeApp, sink) -> None:  # type: ignore[no-untyped-def]
    app = make_app()
    async with app.router.lifespan_context(app):
        pass
    assert any(name == APP_STARTED for name, _ in sink.events)
