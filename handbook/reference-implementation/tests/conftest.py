from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence

import httpx
import pytest
from fastapi import FastAPI

from rag_service.core.config import Settings
from rag_service.core.errors import AppError
from rag_service.core.events import EventSink, EventValue
from rag_service.features.health.service import ReadinessCheck
from rag_service.main import create_app


class RecordingSink:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, EventValue]]] = []

    def emit(self, name: str, props: dict[str, EventValue] | None = None) -> None:  # type: ignore[override]
        self.events.append((name, dict(props or {})))


@pytest.fixture
def sink() -> RecordingSink:
    return RecordingSink()


@pytest.fixture
def make_app(sink: RecordingSink) -> Callable[..., FastAPI]:
    def _make(checks: Sequence[ReadinessCheck] | None = None, **settings: object) -> FastAPI:
        app = create_app(
            Settings(_env_file=None, **({"environment": "test"} | settings)),  # type: ignore[arg-type]
            checks=checks if checks is not None else [],
            events=sink_as_protocol(sink),
            configure_logs=False,
        )

        @app.get("/_apperror")
        async def _apperror() -> None:
            raise AppError("demo_conflict", "Demo conflict", 409, "client-safe detail")

        @app.get("/_boom")
        async def _boom() -> None:
            raise RuntimeError("secret-internal-detail postgresql://user:hunter2@db/x")

        @app.get("/_item/{n}")
        async def _item(n: int) -> dict[str, int]:
            return {"n": n}

        return app

    return _make


def sink_as_protocol(sink: RecordingSink) -> EventSink:
    return sink  # type: ignore[return-value]


@pytest.fixture
async def client_for() -> AsyncIterator[Callable[[FastAPI], httpx.AsyncClient]]:
    clients: list[httpx.AsyncClient] = []

    def _client(app: FastAPI) -> httpx.AsyncClient:
        c = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        )
        clients.append(c)
        return c

    yield _client
    for c in clients:
        await c.aclose()
