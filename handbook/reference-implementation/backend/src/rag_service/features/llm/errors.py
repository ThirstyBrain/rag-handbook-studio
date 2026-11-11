"""Gateway error taxonomy.

Messages are generic on purpose: provider response bodies can echo prompts, and exception text can
carry URLs or keys, so none of it is copied into these exceptions.

``retryable``: trying the same target again may succeed.
``fallback``: trying the next target in the route may succeed.
"""

from __future__ import annotations


class LlmError(Exception):
    retryable: bool = False
    fallback: bool = False

    def __init__(self, message: str, *, provider: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider


class RateLimited(LlmError):
    retryable = True
    fallback = True

    def __init__(
        self, message: str, *, provider: str | None = None, retry_after_s: float | None = None
    ) -> None:
        super().__init__(message, provider=provider)
        self.retry_after_s = retry_after_s


class ProviderUnavailable(LlmError):
    retryable = True
    fallback = True


class ProviderTimeout(LlmError):
    retryable = True
    fallback = True


class ProviderAuthError(LlmError):
    """Bad or missing credentials: retrying is pointless, another provider may work."""

    fallback = True


class TargetUnsupported(LlmError):
    """This provider/model cannot do this (unknown model, no embeddings, endpoint missing).

    A configuration problem for this target only: no retry, but the next target may work.
    """

    fallback = True


class ContentRefused(LlmError):
    """The provider declined for safety reasons. Not retried and not sent to another provider."""


class InvalidRequest(LlmError):
    """The request is wrong for every provider (bad route, empty input, oversized batch)."""


class PolicyViolation(LlmError):
    """No target is allowed for this request (for example restricted data and only external providers)."""


class BudgetExceeded(LlmError):
    """The configured external spend budget is used up and no local target is available."""


class AllTargetsFailed(LlmError):
    def __init__(self, route: str, attempts: list[tuple[str, str, str]]) -> None:
        # attempts: (provider, model, error class name); no messages, no content.
        super().__init__(f"all targets failed for route {route!r}")
        self.route = route
        self.attempts = attempts
