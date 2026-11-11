"""Analytics / domain events. Events carry names and scalar properties only, never user text."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Protocol

from rag_service.core.logging import redact

EventValue = str | int | float | bool

APP_STARTED = "app.started"
READINESS_CHANGED = "health.readiness_changed"


class EventSink(Protocol):
    def emit(self, name: str, props: Mapping[str, EventValue] | None = None) -> None: ...


class LoggingEventSink:
    """Default sink: writes one structured log line per event. Swap for a real pipeline later."""

    def __init__(self) -> None:
        self._log = logging.getLogger("rag.events")

    def emit(self, name: str, props: Mapping[str, EventValue] | None = None) -> None:
        self._log.info("event", extra={"ctx": {"event": name, **redact(props or {})}})
