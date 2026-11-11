"""Gateway behaviour with scriptable fake providers: no network, no model."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
from pydantic import ValidationError

from rag_service.features.llm import (
    AllTargetsFailed,
    BudgetExceeded,
    ChatRequest,
    ContentRefused,
    EmbedRequest,
    GatewayConfig,
    InvalidRequest,
    LlmGateway,
    Message,
    PolicyViolation,
    Sensitivity,
    StreamEnd,
    TextDelta,
    Usage,
)
from rag_service.features.llm.errors import (
    ProviderAuthError,
    ProviderUnavailable,
    RateLimited,
)
from rag_service.features.llm.gateway import build_gateway, build_providers
from rag_service.features.llm.providers.fake import FakeProvider
from rag_service.features.llm.types import StreamEvent

SECRET = "SECRET-PROMPT-TEXT-42"


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def emit(self, name: str, props: dict[str, object] | None = None) -> None:
        self.events.append((name, dict(props or {})))


def make_config(
    chain: list[tuple[str, str]],
    locality: dict[str, str],
    *,
    kind: str = "chat",
    attempts: int = 2,
    prices: dict[str, dict[str, float]] | None = None,
    budget: float | None = None,
    breaker: tuple[int, float] = (5, 30.0),
    max_out: int = 4096,
    max_batch: int = 64,
    spaces: dict[str, str] | None = None,
) -> GatewayConfig:
    targets = []
    for provider, model in chain:
        target: dict[str, object] = {"provider": provider, "model": model}
        if spaces:
            target["embedding_space"] = spaces[provider]
        targets.append(target)
    return GatewayConfig.model_validate(
        {
            "providers": {n: {"kind": "fake", "locality": loc} for n, loc in locality.items()},
            "routes": {
                "answer" if kind == "chat" else "embed": {
                    "kind": kind,
                    "chain": targets,
                    "max_attempts_per_target": attempts,
                    "timeout_s": 5,
                    "max_output_tokens": max_out,
                    "max_batch": max_batch,
                }
            },
            "prices": prices or {},
            "external_daily_budget_usd": budget,
            "breaker": {"failure_threshold": breaker[0], "reset_after_s": breaker[1]},
            "backoff": {"base_s": 0.5, "cap_s": 8.0},
        }
    )


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def gateway(
    config: GatewayConfig,
    providers: dict[str, FakeProvider],
    rec: Recorder,
    sleeps: list[float] | None = None,
    clock: Clock | None = None,
    today: date | None = None,
) -> LlmGateway:
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return LlmGateway(
        config,
        providers,  # type: ignore[arg-type]
        events=rec,  # type: ignore[arg-type]
        clock=clock or Clock(),
        sleep=fake_sleep,
        rng=lambda: 1.0,  # jitter factor 1.0 -> deterministic delays
        today=(lambda: today) if today else (lambda: date(2026, 11, 8)),
    )


def chat(sensitivity: Sensitivity = Sensitivity.INTERNAL, max_tokens: int = 100) -> ChatRequest:
    return ChatRequest(
        route="answer",
        messages=[Message(role="user", content=SECRET)],
        max_output_tokens=max_tokens,
        sensitivity=sensitivity,
    )


LOCAL_FIRST = [("local", "m-local"), ("cloud", "m-cloud")]
LOC = {"local": "local", "cloud": "external"}

# ------------------------------------------------------------------ happy path, retry, fallback


async def test_first_target_succeeds_and_emits_content_free_event() -> None:
    rec = Recorder()
    local, cloud = FakeProvider("local"), FakeProvider("cloud", locality="external")
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, rec)
    result = await gw.chat(chat())
    assert result.provider == "local" and result.attempts == 1 and not result.fallback_used
    assert cloud.calls == []
    assert [n for n, _ in rec.events] == ["llm.call"]
    assert rec.events[0][1]["outcome"] == "ok" and SECRET not in str(rec.events)


async def test_retry_on_transient_error_with_backoff() -> None:
    sleeps: list[float] = []
    local = FakeProvider("local", outcomes=[ProviderUnavailable("x"), "recovered"])
    gw = gateway(
        make_config(LOCAL_FIRST, LOC),
        {"local": local, "cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
        sleeps,
    )
    result = await gw.chat(chat())
    assert result.text == "recovered" and result.attempts == 2 and result.provider == "local"
    assert sleeps == [0.5]  # base_s * 2**0 * jitter(1.0)


async def test_fallback_after_retries_exhausted() -> None:
    local = FakeProvider("local", outcomes=[ProviderUnavailable("x"), ProviderUnavailable("x")])
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, Recorder())
    result = await gw.chat(chat())
    assert result.provider == "cloud" and result.fallback_used and result.attempts == 3
    assert len(local.calls) == 2 and len(cloud.calls) == 1


async def test_invalid_request_is_not_retried_or_sent_elsewhere() -> None:
    local = FakeProvider("local", outcomes=[InvalidRequest("bad")])
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, Recorder())
    with pytest.raises(InvalidRequest):
        await gw.chat(chat())
    assert len(local.calls) == 1 and cloud.calls == []


async def test_refusal_is_not_forwarded_to_another_provider() -> None:
    local = FakeProvider("local", outcomes=[ContentRefused("declined")])
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, Recorder())
    with pytest.raises(ContentRefused):
        await gw.chat(chat())
    assert cloud.calls == []


async def test_auth_error_skips_retry_but_falls_back() -> None:
    local = FakeProvider("local", outcomes=[ProviderAuthError("denied")])
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, Recorder())
    result = await gw.chat(chat())
    assert len(local.calls) == 1 and result.provider == "cloud"


async def test_rate_limit_honours_retry_after_up_to_cap() -> None:
    sleeps: list[float] = []
    local = FakeProvider("local", outcomes=[RateLimited("slow down", retry_after_s=3.0), "ok"])
    gw = gateway(
        make_config(LOCAL_FIRST, LOC),
        {"local": local, "cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
        sleeps,
    )
    await gw.chat(chat())
    assert sleeps == [3.0]
    sleeps.clear()
    local2 = FakeProvider("local", outcomes=[RateLimited("slow down", retry_after_s=999.0), "ok"])
    gw2 = gateway(
        make_config(LOCAL_FIRST, LOC),
        {"local": local2, "cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
        sleeps,
    )
    await gw2.chat(chat())
    assert sleeps == [8.0]  # capped by backoff.cap_s


async def test_all_targets_fail_without_leaking_content() -> None:
    rec = Recorder()
    boom = [ProviderUnavailable("down")] * 2
    gw = gateway(
        make_config(LOCAL_FIRST, LOC),
        {
            "local": FakeProvider("local", outcomes=list(boom)),
            "cloud": FakeProvider("cloud", locality="external", outcomes=list(boom)),
        },
        rec,
    )
    with pytest.raises(AllTargetsFailed) as info:
        await gw.chat(chat())
    assert [a[0] for a in info.value.attempts] == ["local", "local", "cloud", "cloud"]
    assert SECRET not in str(info.value) and SECRET not in str(rec.events)


async def test_unexpected_provider_exception_is_contained() -> None:
    class Buggy(FakeProvider):
        async def chat(self, model, request):  # type: ignore[no-untyped-def,override]
            raise RuntimeError(f"internal detail {SECRET} postgresql://u:pw@h/db")

    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(
        make_config(LOCAL_FIRST, LOC, attempts=1),
        {"local": Buggy("local"), "cloud": cloud},
        Recorder(),
    )
    result = await gw.chat(chat())
    assert result.provider == "cloud"


# ------------------------------------------------------------------ policy


async def test_restricted_data_never_reaches_external_providers() -> None:
    local = FakeProvider("local", outcomes=[ProviderUnavailable("x"), ProviderUnavailable("x")])
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, Recorder())
    with pytest.raises(AllTargetsFailed):
        await gw.chat(chat(Sensitivity.RESTRICTED))
    assert cloud.calls == [], "restricted data must not fall back to an external provider"


async def test_restricted_with_only_external_targets_fails_closed() -> None:
    cfg = make_config([("cloud", "m")], {"cloud": "external"})
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(cfg, {"cloud": cloud}, Recorder())
    with pytest.raises(PolicyViolation):
        await gw.chat(chat(Sensitivity.RESTRICTED))
    assert cloud.calls == []


async def test_public_data_may_use_external_first_if_configured() -> None:
    cfg = make_config([("cloud", "m")], {"cloud": "external"})
    gw = gateway(cfg, {"cloud": FakeProvider("cloud", locality="external")}, Recorder())
    assert (await gw.chat(chat(Sensitivity.PUBLIC))).provider == "cloud"


async def test_token_cap_and_temperature_stripping() -> None:
    local = FakeProvider("local")
    local.supports_temperature = False
    gw = gateway(
        make_config(LOCAL_FIRST, LOC, max_out=100),
        {"local": local, "cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
    )
    req = chat(max_tokens=100_000).model_copy(update={"temperature": 0.7})
    await gw.chat(req)
    assert local.seen_max_tokens == [100] and local.seen_temperatures == [None]


async def test_unknown_route_and_wrong_kind() -> None:
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": FakeProvider("local")}, Recorder())
    with pytest.raises(InvalidRequest):
        await gw.chat(ChatRequest(route="nope", messages=[Message(role="user", content="x")]))
    with pytest.raises(InvalidRequest):
        await gw.embed(EmbedRequest(route="answer", inputs=["x"]))


# ------------------------------------------------------------------ circuit breaker


async def test_breaker_opens_then_half_opens() -> None:
    clock = Clock()
    cfg = make_config(LOCAL_FIRST, LOC, attempts=1, breaker=(2, 30.0))
    bad = [ProviderUnavailable("x")] * 3
    local = FakeProvider("local", outcomes=list(bad))
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(cfg, {"local": local, "cloud": cloud}, Recorder(), clock=clock)
    await gw.chat(chat())
    await gw.chat(chat())  # second consecutive failure opens the breaker
    assert len(local.calls) == 2
    await gw.chat(chat())  # breaker open: local is skipped without being called
    assert len(local.calls) == 2 and gw.status()["local"]["breaker_open"] is True
    clock.now += 31  # reset window passed: one probe is allowed (still scripted to fail)
    await gw.chat(chat())
    assert len(local.calls) == 3 and gw.status()["local"]["breaker_open"] is True
    clock.now += 31  # next probe succeeds (script exhausted) and closes the breaker
    result = await gw.chat(chat())
    assert result.provider == "local" and gw.status()["local"]["breaker_open"] is False


# ------------------------------------------------------------------ budget and cost

PRICES = {"cloud/m-cloud": {"input_per_mtok": 1000.0, "output_per_mtok": 1000.0}}


async def test_cost_estimation_from_operator_prices() -> None:
    cfg = make_config([("cloud", "m-cloud")], {"cloud": "external"}, prices=PRICES)
    gw = gateway(
        cfg, {"cloud": FakeProvider("cloud", locality="external", outcomes=["x" * 400])}, Recorder()
    )
    result = await gw.chat(chat())
    expected = (result.usage.input_tokens + result.usage.output_tokens) * 1000.0 / 1e6
    assert result.estimated_cost_usd == pytest.approx(expected) and expected > 0


async def test_local_cost_is_zero_and_external_without_price_is_unknown() -> None:
    gw = gateway(
        make_config(LOCAL_FIRST, LOC),
        {"local": FakeProvider("local"), "cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
    )
    assert (await gw.chat(chat())).estimated_cost_usd == 0.0
    gw2 = gateway(
        make_config([("cloud", "m-cloud")], {"cloud": "external"}),
        {"cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
    )
    assert (await gw2.chat(chat())).estimated_cost_usd is None


async def test_budget_exhausted_falls_back_to_local_then_resets_next_day() -> None:
    day = {"d": date(2026, 11, 8)}
    cfg = make_config(
        [("cloud", "m-cloud"), ("local", "m-local")], LOC, prices=PRICES, budget=0.0001
    )
    cloud, local = FakeProvider("cloud", locality="external"), FakeProvider("local")
    rec = Recorder()
    gw = LlmGateway(cfg, {"cloud": cloud, "local": local}, events=rec, today=lambda: day["d"])  # type: ignore[arg-type]
    first = await gw.chat(chat())
    assert first.provider == "cloud"  # budget not yet used
    second = await gw.chat(chat())
    assert second.provider == "local", (
        "once the daily budget is spent, external targets are skipped"
    )
    day["d"] = date(2026, 11, 9)
    third = await gw.chat(chat())
    assert third.provider == "cloud", "the budget resets on a new UTC day"


async def test_budget_exhausted_without_local_target_raises() -> None:
    cfg = make_config([("cloud", "m-cloud")], {"cloud": "external"}, prices=PRICES, budget=0.0001)
    gw = gateway(cfg, {"cloud": FakeProvider("cloud", locality="external")}, Recorder())
    await gw.chat(chat())
    with pytest.raises(BudgetExceeded):
        await gw.chat(chat())


async def test_external_target_with_unknown_price_is_not_used_under_a_budget() -> None:
    cfg = make_config(
        [("cloud", "m-cloud"), ("local", "m-local")], LOC, budget=10.0
    )  # no prices configured
    cloud, local = FakeProvider("cloud", locality="external"), FakeProvider("local")
    gw = gateway(cfg, {"cloud": cloud, "local": local}, Recorder())
    assert (await gw.chat(chat())).provider == "local" and cloud.calls == []


# ------------------------------------------------------------------ embeddings

SPACE_CFG = dict(kind="embed", spaces={"local": "space-a", "cloud": "space-a"})


async def test_embed_returns_vectors_and_space() -> None:
    gw = gateway(
        make_config(LOCAL_FIRST, LOC, **SPACE_CFG),
        {"local": FakeProvider("local"), "cloud": FakeProvider("cloud", locality="external")},
        Recorder(),
    )  # type: ignore[arg-type]
    result = await gw.embed(EmbedRequest(route="embed", inputs=["a", "b"]))
    assert (
        len(result.vectors) == 2
        and result.dimensions == len(result.vectors[0])
        and result.embedding_space == "space-a"
    )


async def test_embed_batch_limit_and_fallback() -> None:
    cfg = make_config(LOCAL_FIRST, LOC, max_batch=2, **SPACE_CFG)  # type: ignore[arg-type]
    local = FakeProvider("local", outcomes=[ProviderUnavailable("x"), ProviderUnavailable("x")])
    gw = gateway(
        cfg, {"local": local, "cloud": FakeProvider("cloud", locality="external")}, Recorder()
    )
    with pytest.raises(InvalidRequest):
        await gw.embed(EmbedRequest(route="embed", inputs=["a", "b", "c"]))
    result = await gw.embed(EmbedRequest(route="embed", inputs=["a"]))
    assert result.provider == "cloud" and result.fallback_used


async def test_embed_rejects_inconsistent_dimensions_from_a_provider() -> None:
    class Ragged(FakeProvider):
        async def embed(self, model, inputs):  # type: ignore[no-untyped-def,override]
            return [[0.1, 0.2], [0.3]], Usage()

    cfg = make_config(
        [("local", "m")], {"local": "local"}, kind="embed", spaces={"local": "s"}, attempts=1
    )
    gw = gateway(cfg, {"local": Ragged("local")}, Recorder())
    with pytest.raises(ProviderUnavailable):
        await gw.embed(EmbedRequest(route="embed", inputs=["a", "b"]))


async def test_embed_route_must_not_mix_embedding_spaces() -> None:
    with pytest.raises(ValidationError):
        make_config(LOCAL_FIRST, LOC, kind="embed", spaces={"local": "space-a", "cloud": "space-b"})
    with pytest.raises(ValidationError):
        make_config(LOCAL_FIRST, LOC, kind="embed")  # spaces missing entirely


# ------------------------------------------------------------------ streaming


async def collect(gen: AsyncIterator[StreamEvent]) -> list[StreamEvent]:
    return [e async for e in gen]


async def test_stream_yields_deltas_then_enriched_end() -> None:
    gw = gateway(
        make_config(LOCAL_FIRST, LOC),
        {
            "local": FakeProvider("local", outcomes=["one two three"]),
            "cloud": FakeProvider("cloud", locality="external"),
        },
        Recorder(),
    )
    events = await collect(gw.stream(chat()))
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["one ", "two ", "three "]
    end = events[-1]
    assert (
        isinstance(end, StreamEnd) and end.result.provider == "local" and end.result.attempts == 1
    )


async def test_stream_falls_back_before_first_token() -> None:
    local = FakeProvider("local", outcomes=[ProviderUnavailable("x"), ProviderUnavailable("x")])
    cloud = FakeProvider("cloud", locality="external", outcomes=["hello world"])
    gw = gateway(make_config(LOCAL_FIRST, LOC), {"local": local, "cloud": cloud}, Recorder())
    events = await collect(gw.stream(chat()))
    end = events[-1]
    assert (
        isinstance(end, StreamEnd) and end.result.provider == "cloud" and end.result.fallback_used
    )


async def test_stream_error_after_first_token_propagates_without_fallback() -> None:
    class Midway(FakeProvider):
        async def stream(self, model, request):  # type: ignore[no-untyped-def,override]
            yield TextDelta(text="partial ")
            raise ProviderUnavailable("connection dropped")

    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(
        make_config(LOCAL_FIRST, LOC), {"local": Midway("local"), "cloud": cloud}, Recorder()
    )
    seen: list[str] = []
    with pytest.raises(ProviderUnavailable):
        async for event in gw.stream(chat()):
            if isinstance(event, TextDelta):
                seen.append(event.text)
    assert seen == ["partial "] and cloud.calls == []


async def test_stream_restricted_never_uses_external() -> None:
    cfg = make_config([("cloud", "m")], {"cloud": "external"})
    cloud = FakeProvider("cloud", locality="external")
    gw = gateway(cfg, {"cloud": cloud}, Recorder())
    with pytest.raises(PolicyViolation):
        await collect(gw.stream(chat(Sensitivity.RESTRICTED)))
    assert cloud.calls == []


# ------------------------------------------------------------------ building from configuration


def test_build_providers_reports_missing_keys_and_blocks_fake_in_production() -> None:
    cfg = GatewayConfig.model_validate(
        {
            "providers": {
                "claude": {"kind": "anthropic", "locality": "external", "api_key_env": "NOPE_KEY"},
                "dev": {"kind": "fake", "locality": "local"},
                "ollama": {
                    "kind": "openai_compat",
                    "locality": "local",
                    "base_url": "http://127.0.0.1:1/v1",
                },
            },
            "routes": {
                "answer": {
                    "chain": [
                        {"provider": "claude", "model": "m"},
                        {"provider": "dev", "model": "m"},
                        {"provider": "ollama", "model": "m"},
                    ]
                }
            },
        }
    )
    providers, unavailable = build_providers(cfg, env={}, allow_fake=False)
    assert set(providers) == {"ollama"}
    assert "NOPE_KEY" in unavailable["claude"] and "not allowed" in unavailable["dev"]
    providers2, _ = build_providers(cfg, env={"NOPE_KEY": "k"}, allow_fake=True)
    assert set(providers2) == {"claude", "dev", "ollama"}


def test_strict_mode_refuses_routes_without_usable_provider() -> None:
    cfg = GatewayConfig.model_validate(
        {
            "providers": {
                "claude": {"kind": "anthropic", "locality": "external", "api_key_env": "NOPE_KEY"}
            },
            "routes": {"answer": {"chain": [{"provider": "claude", "model": "m"}]}},
            "strict": True,
        }
    )
    with pytest.raises(RuntimeError, match="answer"):
        build_gateway(cfg, env={})
    non_strict = cfg.model_copy(update={"strict": False})
    gw = build_gateway(non_strict, env={})
    assert gw.status()["claude"]["available"] is False and "NOPE_KEY" in str(
        gw.status()["claude"]["reason"]
    )
