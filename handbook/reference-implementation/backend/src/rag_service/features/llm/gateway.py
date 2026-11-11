"""The LLM gateway: the only thing application code talks to.

Application code names a *route* (a purpose). The configuration maps routes to an ordered chain of
(provider, model) targets, typically local first and external as fallback. The gateway adds, uniformly
for every provider: timeouts, bounded retries with backoff, fallback, a circuit breaker per provider,
a data-sensitivity policy (restricted data never leaves local providers), an optional external spend
budget, token caps, cost estimation from operator-supplied prices, and content-free usage events.

Streaming can retry and fall back only *before the first token*; after that, errors propagate.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Literal, TypeVar

from rag_service.core.events import EventSink, EventValue, LoggingEventSink
from rag_service.features.llm.config import GatewayConfig, RouteConfig, Target
from rag_service.features.llm.errors import (
    AllTargetsFailed,
    BudgetExceeded,
    InvalidRequest,
    LlmError,
    PolicyViolation,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimited,
)
from rag_service.features.llm.ports import LlmProvider
from rag_service.features.llm.providers.anthropic import AnthropicProvider
from rag_service.features.llm.providers.fake import FakeProvider
from rag_service.features.llm.providers.openai_compat import OpenAICompatProvider
from rag_service.features.llm.types import (
    ChatRequest,
    ChatResult,
    EmbedRequest,
    EmbedResult,
    Sensitivity,
    StreamEnd,
    StreamEvent,
    Usage,
)

_log = logging.getLogger(__name__)
T = TypeVar("T")
Clock = Callable[[], float]


class CircuitBreaker:
    """Opens after N consecutive failures, allows one probe after ``reset_after_s``."""

    def __init__(self, threshold: int, reset_after_s: float, clock: Clock) -> None:
        self._threshold = threshold
        self._reset = reset_after_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    @property
    def is_open(self) -> bool:
        return self._opened_at is not None

    def allow(self) -> bool:
        if self._opened_at is None:
            return True
        if self._probing or self._clock() - self._opened_at < self._reset:
            return False
        self._probing = True  # half-open: exactly one trial call
        return True

    def success(self) -> None:
        self._failures, self._opened_at, self._probing = 0, None, False

    def failure(self) -> None:
        self._failures += 1
        if self._probing or self._failures >= self._threshold:
            self._opened_at, self._probing = self._clock(), False

    def neutral(self) -> None:
        """A call ended in a way that says nothing about provider health (for example a bad request)."""
        self._probing = False


class SpendLedger:
    """In-memory external spend per UTC day. Best effort: restarts reset it, concurrent calls may overshoot."""

    def __init__(self, today: Callable[[], date]) -> None:
        self._today = today
        self._day = today()
        self._spent = 0.0

    def _roll(self) -> None:
        if self._today() != self._day:
            self._day, self._spent = self._today(), 0.0

    @property
    def spent_today(self) -> float:
        self._roll()
        return self._spent

    def add(self, amount: float) -> None:
        self._roll()
        self._spent += amount


class LlmGateway:
    def __init__(
        self,
        config: GatewayConfig,
        providers: Mapping[str, LlmProvider],
        *,
        unavailable: Mapping[str, str] | None = None,
        events: EventSink | None = None,
        clock: Clock = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: Callable[[], float] = random.random,
        today: Callable[[], date] = lambda: datetime.now(UTC).date(),
    ) -> None:
        self._config = config
        self._providers = dict(providers)
        self.unavailable = dict(unavailable or {})
        self._events = events or LoggingEventSink()
        self._sleep = sleep
        self._rng = rng
        self._breakers = {
            name: CircuitBreaker(
                config.breaker.failure_threshold, config.breaker.reset_after_s, clock
            )
            for name in self._providers
        }
        self._ledger = SpendLedger(today)

    # ------------------------------------------------------------------ public API

    async def chat(self, request: ChatRequest) -> ChatResult:
        route = self._route(request.route, "chat")
        req = self._capped(request, route)
        result, target, attempts = await self._execute(
            request.route,
            route,
            request.sensitivity,
            "chat",
            lambda p, t: p.chat(t.model, self._for(p, req)),
        )
        return self._finish_chat(request.route, route, target, result, attempts)

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        route = self._route(request.route, "chat")
        req = self._capped(request, route)
        targets, reasons = self._candidates(route, request.sensitivity, "chat")
        if not targets:
            raise self._no_target_error(request.route, reasons)
        failures: list[tuple[str, str, str]] = []
        total_attempts = 0
        for target in targets:
            provider = self._providers[target.provider]
            breaker = self._breakers[target.provider]
            if not breaker.allow():
                failures.append((target.provider, target.model, "breaker_open"))
                continue
            for attempt in range(1, route.max_attempts_per_target + 1):
                total_attempts += 1
                started_yield = False
                events = provider.stream(target.model, self._for(provider, req))
                try:
                    while True:
                        try:
                            async with asyncio.timeout(route.timeout_s):
                                event = await anext(events)
                        except StopAsyncIteration:
                            break
                        if isinstance(event, StreamEnd):
                            breaker.success()
                            yield StreamEnd(
                                result=self._finish_chat(
                                    request.route, route, target, event.result, total_attempts
                                )
                            )
                            return
                        started_yield = True
                        yield event
                    raise ProviderUnavailable(
                        "stream ended without a final event", provider=target.provider
                    )
                except Exception as exc:
                    err = self._classify(exc, target.provider)
                    if started_yield:
                        breaker.failure()
                        self._emit_failure(request.route, target, err)
                        raise err from None
                    decision = await self._decide(
                        err, breaker, attempt, route.max_attempts_per_target
                    )
                    failures.append((target.provider, target.model, type(err).__name__))
                    if decision == "next":
                        break
                finally:
                    await events.aclose()  # type: ignore[attr-defined]
        raise AllTargetsFailed(request.route, failures)

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        route = self._route(request.route, "embed")
        if len(request.inputs) > route.max_batch:
            raise InvalidRequest(
                f"batch of {len(request.inputs)} exceeds the route limit {route.max_batch}"
            )
        (vectors, usage), target, attempts = await self._execute(
            request.route,
            route,
            request.sensitivity,
            "embed",
            lambda p, t: p.embed(t.model, request.inputs),
        )
        dims = {len(v) for v in vectors}
        if len(dims) != 1:
            raise ProviderUnavailable("inconsistent embedding dimensions", provider=target.provider)
        cost = self._cost(target, usage)
        self._emit_success(request.route, route, target, "embed", usage, 0.0, attempts, cost)
        return EmbedResult(
            vectors=vectors,
            usage=usage,
            provider=target.provider,
            model=target.model,
            embedding_space=target.embedding_space or "",
            dimensions=dims.pop(),
            latency_ms=0.0,
            attempts=attempts,
            fallback_used=target is not route.chain[0],
            estimated_cost_usd=cost,
        )

    async def aclose(self) -> None:
        for provider in self._providers.values():
            await provider.aclose()

    def status(self) -> dict[str, dict[str, object]]:
        """Content-free diagnostics: provider availability and breaker state."""
        out: dict[str, dict[str, object]] = {}
        for name in self._config.providers:
            if name in self._providers:
                out[name] = {"available": True, "breaker_open": self._breakers[name].is_open}
            else:
                out[name] = {"available": False, "reason": self.unavailable.get(name, "unknown")}
        return out

    # ------------------------------------------------------------------ internals

    def _route(self, name: str, kind: Literal["chat", "embed"]) -> RouteConfig:
        route = self._config.routes.get(name)
        if route is None:
            raise InvalidRequest(f"unknown route {name!r}")
        if route.kind != kind:
            raise InvalidRequest(f"route {name!r} is a {route.kind} route, not {kind}")
        return route

    @staticmethod
    def _capped(request: ChatRequest, route: RouteConfig) -> ChatRequest:
        if request.max_output_tokens <= route.max_output_tokens:
            return request
        return request.model_copy(update={"max_output_tokens": route.max_output_tokens})

    @staticmethod
    def _for(provider: LlmProvider, request: ChatRequest) -> ChatRequest:
        if request.temperature is not None and not provider.supports_temperature:
            return request.model_copy(update={"temperature": None})
        return request

    def _price_known(self, target: Target) -> bool:
        return f"{target.provider}/{target.model}" in self._config.prices

    def _candidates(
        self, route: RouteConfig, sensitivity: Sensitivity, need: Literal["chat", "embed"]
    ) -> tuple[list[Target], dict[str, int]]:
        reasons: dict[str, int] = {}
        eligible: list[Target] = []
        budget = self._config.external_daily_budget_usd
        for target in route.chain:
            provider = self._providers.get(target.provider)
            reason: str | None = None
            if provider is None:
                reason = "unavailable"
            elif (need == "chat" and not provider.supports_chat) or (
                need == "embed" and not provider.supports_embeddings
            ):
                reason = "capability"
            elif sensitivity is Sensitivity.RESTRICTED and provider.locality != "local":
                reason = "policy"
            elif provider.locality == "external" and budget is not None:
                if not self._price_known(target):
                    reason = "budget"  # cannot account for the spend, so do not spend
                elif self._ledger.spent_today >= budget:
                    reason = "budget"
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
            else:
                eligible.append(target)
        return eligible, reasons

    @staticmethod
    def _no_target_error(route: str, reasons: dict[str, int]) -> LlmError:
        if reasons.get("policy") and set(reasons) <= {"policy", "unavailable", "capability"}:
            return PolicyViolation(f"no provider on route {route!r} may receive restricted data")
        if reasons.get("budget") and set(reasons) <= {"budget", "unavailable", "capability"}:
            return BudgetExceeded(
                f"external budget exhausted and no local target on route {route!r}"
            )
        return AllTargetsFailed(route, [])

    def _classify(self, exc: Exception, provider: str) -> LlmError:
        if isinstance(exc, LlmError):
            return exc
        if isinstance(exc, TimeoutError):
            return ProviderTimeout("provider timed out", provider=provider)
        _log.warning(
            "provider_unexpected_error",
            extra={"ctx": {"provider": provider, "type": type(exc).__name__}},
        )
        return ProviderUnavailable("unexpected provider failure", provider=provider)

    def _delay(self, err: LlmError, attempt: int) -> float:
        cfg = self._config.backoff
        delay = min(cfg.cap_s, cfg.base_s * 2.0 ** (attempt - 1)) * (0.5 + self._rng() / 2)
        if isinstance(err, RateLimited) and err.retry_after_s is not None:
            delay = max(delay, min(err.retry_after_s, cfg.cap_s))
        return delay

    async def _decide(
        self, err: LlmError, breaker: CircuitBreaker, attempt: int, max_attempts: int
    ) -> Literal["retry", "next"]:
        if not (err.fallback or err.retryable):
            breaker.neutral()
            raise err  # the request itself is the problem, or the provider refused: no retry, no other provider
        breaker.failure()
        if err.retryable and attempt < max_attempts:
            await self._sleep(self._delay(err, attempt))
            return "retry"
        return "next"

    async def _execute(
        self,
        route_name: str,
        route: RouteConfig,
        sensitivity: Sensitivity,
        need: Literal["chat", "embed"],
        operation: Callable[[LlmProvider, Target], Awaitable[T]],
    ) -> tuple[T, Target, int]:
        targets, reasons = self._candidates(route, sensitivity, need)
        if not targets:
            raise self._no_target_error(route_name, reasons)
        failures: list[tuple[str, str, str]] = []
        attempts = 0
        for target in targets:
            provider = self._providers[target.provider]
            breaker = self._breakers[target.provider]
            if not breaker.allow():
                failures.append((target.provider, target.model, "breaker_open"))
                continue
            for attempt in range(1, route.max_attempts_per_target + 1):
                attempts += 1
                try:
                    async with asyncio.timeout(route.timeout_s):
                        result = await operation(provider, target)
                except Exception as exc:
                    err = self._classify(exc, target.provider)
                    try:
                        decision = await self._decide(
                            err, breaker, attempt, route.max_attempts_per_target
                        )
                    except LlmError:
                        self._emit_failure(route_name, target, err)
                        raise
                    failures.append((target.provider, target.model, type(err).__name__))
                    if decision == "next":
                        break
                else:
                    breaker.success()
                    return result, target, attempts
        self._emit_failure(route_name, route.chain[-1], AllTargetsFailed(route_name, failures))
        raise AllTargetsFailed(route_name, failures)

    def _cost(self, target: Target, usage: Usage) -> float | None:
        price = self._config.prices.get(f"{target.provider}/{target.model}")
        provider = self._providers[target.provider]
        if price is None:
            return 0.0 if provider.locality == "local" else None
        cost = (
            usage.input_tokens * price.input_per_mtok / 1e6
            + usage.output_tokens * price.output_per_mtok / 1e6
        )
        if provider.locality == "external":
            self._ledger.add(cost)
        return cost

    def _finish_chat(
        self, route_name: str, route: RouteConfig, target: Target, result: ChatResult, attempts: int
    ) -> ChatResult:
        cost = self._cost(target, result.usage)
        self._emit_success(
            route_name, route, target, "chat", result.usage, result.latency_ms, attempts, cost
        )
        return result.model_copy(
            update={
                "attempts": attempts,
                "fallback_used": target is not route.chain[0],
                "estimated_cost_usd": cost,
            }
        )

    def _emit_success(
        self,
        route_name: str,
        route: RouteConfig,
        target: Target,
        op: str,
        usage: Usage,
        latency_ms: float,
        attempts: int,
        cost: float | None,
    ) -> None:
        props: dict[str, EventValue] = {
            "route": route_name,
            "operation": op,
            "provider": target.provider,
            "model": target.model,
            "outcome": "ok",
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "latency_ms": latency_ms,
            "attempts": attempts,
            "fallback_used": target is not route.chain[0],
        }
        if cost is not None:
            props["cost_usd"] = round(cost, 8)
        self._events.emit("llm.call", props)

    def _emit_failure(self, route_name: str, target: Target, err: LlmError) -> None:
        self._events.emit(
            "llm.call",
            {
                "route": route_name,
                "provider": target.provider,
                "model": target.model,
                "outcome": type(err).__name__,
            },
        )


def build_providers(
    config: GatewayConfig, env: Mapping[str, str] | None = None, *, allow_fake: bool = False
) -> tuple[dict[str, LlmProvider], dict[str, str]]:
    """Instantiate providers from configuration. A provider that cannot be built is reported, not fatal."""
    env = os.environ if env is None else env
    providers: dict[str, LlmProvider] = {}
    unavailable: dict[str, str] = {}
    for name, pc in config.providers.items():
        key = env.get(pc.api_key_env) if pc.api_key_env else None
        if pc.api_key_env and not key:
            unavailable[name] = f"environment variable {pc.api_key_env} is not set"
            continue
        try:
            if pc.kind == "fake":
                if not allow_fake:
                    unavailable[name] = "fake provider is not allowed in this environment"
                    continue
                providers[name] = FakeProvider(name, locality=pc.locality)
            elif pc.kind == "anthropic":
                providers[name] = AnthropicProvider(
                    name, api_key=key, locality=pc.locality, base_url=pc.base_url
                )
            else:
                if not pc.base_url:
                    unavailable[name] = "base_url is required for openai_compat providers"
                    continue
                providers[name] = OpenAICompatProvider(
                    name,
                    base_url=pc.base_url,
                    locality=pc.locality,
                    api_key=key,
                    max_tokens_param=pc.max_tokens_param,
                    stream_include_usage=pc.stream_include_usage,
                )
        except Exception as exc:
            unavailable[name] = f"could not be constructed ({type(exc).__name__})"
    return providers, unavailable


def build_gateway(
    config: GatewayConfig,
    env: Mapping[str, str] | None = None,
    *,
    allow_fake: bool = False,
    events: EventSink | None = None,
) -> LlmGateway:
    providers, unavailable = build_providers(config, env, allow_fake=allow_fake)
    for name, reason in unavailable.items():
        _log.warning(
            "llm_provider_unavailable", extra={"ctx": {"provider": name, "reason": reason}}
        )
    if config.strict:
        empty = [
            r
            for r, rc in config.routes.items()
            if not any(t.provider in providers for t in rc.chain)
        ]
        if empty:
            raise RuntimeError(f"strict mode: routes without any usable provider: {sorted(empty)}")
    return LlmGateway(config, providers, unavailable=unavailable, events=events)


def route_names(
    config: GatewayConfig, kind: Literal["chat", "embed"] | None = None
) -> Sequence[str]:
    return [n for n, r in config.routes.items() if kind is None or r.kind == kind]
