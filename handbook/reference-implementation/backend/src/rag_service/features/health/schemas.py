from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class CheckStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"


class CheckResult(BaseModel):
    status: CheckStatus
    latency_ms: float
    # Generic reason only ("timeout", "unavailable"). Never exception text, hostnames or DSNs.
    detail: str | None = None


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "down"]
    checks: dict[str, CheckResult]
