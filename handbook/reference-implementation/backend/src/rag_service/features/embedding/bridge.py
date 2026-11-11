"""Run coroutines from synchronous code on one long-lived event loop.

The worker is synchronous (one job at a time, ADR-015) but the gateway is asynchronous and its HTTP
clients are bound to the loop that created them, so ``asyncio.run`` per job would break the second job.
A single background loop thread keeps those clients valid for the life of the process.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncBridge:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="async-bridge", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Coroutine[Any, Any, T], timeout_s: float) -> T:
        """Run ``coro`` on the loop and wait at most ``timeout_s``; on timeout the coroutine is cancelled."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout_s)
        except TimeoutError:
            future.cancel()
            raise

    def close(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if not self._thread.is_alive():
            self._loop.close()
