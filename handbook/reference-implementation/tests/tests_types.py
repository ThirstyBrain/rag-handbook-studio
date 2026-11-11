"""Type aliases shared by test modules."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi import FastAPI

MakeApp = Callable[..., FastAPI]
ClientFor = Callable[[FastAPI], httpx.AsyncClient]
