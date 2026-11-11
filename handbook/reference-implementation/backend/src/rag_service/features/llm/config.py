"""Gateway configuration, loaded from a TOML file (stdlib ``tomllib``; no extra dependency).

The file names providers, routes and optional prices. It never contains secrets: a provider points at
an environment variable (``api_key_env``) and the gateway reads the value at start-up.
Model identifiers live here, never in application code.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderConfig(_Strict):
    kind: Literal["anthropic", "openai_compat", "fake"]
    locality: Literal["local", "external"]
    base_url: str | None = None
    api_key_env: str | None = None
    # openai_compat only: some servers want max_completion_tokens instead of max_tokens.
    max_tokens_param: Literal["max_tokens", "max_completion_tokens"] = "max_tokens"
    # openai_compat only: send stream_options.include_usage (needed to count streamed tokens).
    stream_include_usage: bool = True


class Target(_Strict):
    provider: str
    model: str
    # Embedding routes only: targets in one route must share an embedding space (same model family and
    # dimensionality), because vectors from different models are not comparable.
    embedding_space: str | None = None


class RouteConfig(_Strict):
    kind: Literal["chat", "embed"] = "chat"
    chain: list[Target] = Field(min_length=1)
    max_attempts_per_target: int = Field(default=2, ge=1, le=5)
    timeout_s: float = Field(default=60.0, gt=0, le=600)
    max_output_tokens: int = Field(default=4096, gt=0)
    max_batch: int = Field(default=64, gt=0)

    @model_validator(mode="after")
    def _embedding_chain_shares_space(self) -> Self:
        if self.kind == "embed":
            spaces = {t.embedding_space for t in self.chain}
            if None in spaces or len(spaces) != 1:
                raise ValueError(
                    "every target of an embed route must declare the same embedding_space; "
                    "vectors from different models cannot be mixed in one index"
                )
        return self


class Price(_Strict):
    """Operator-supplied price in USD per million tokens. The repository ships no prices."""

    input_per_mtok: float = Field(ge=0)
    output_per_mtok: float = Field(default=0.0, ge=0)


class BreakerConfig(_Strict):
    failure_threshold: int = Field(default=5, ge=1)
    reset_after_s: float = Field(default=30.0, gt=0)


class BackoffConfig(_Strict):
    base_s: float = Field(default=0.5, ge=0)
    cap_s: float = Field(default=8.0, ge=0)


class GatewayConfig(_Strict):
    providers: dict[str, ProviderConfig]
    routes: dict[str, RouteConfig]
    prices: dict[str, Price] = Field(default_factory=dict)  # key: "provider/model"
    breaker: BreakerConfig = Field(default_factory=BreakerConfig)
    backoff: BackoffConfig = Field(default_factory=BackoffConfig)
    external_daily_budget_usd: float | None = Field(default=None, gt=0)
    # True: refuse to start when a route has no usable provider (recommended in production).
    strict: bool = False

    @model_validator(mode="after")
    def _targets_reference_known_providers(self) -> Self:
        for route_name, route in self.routes.items():
            for target in route.chain:
                if target.provider not in self.providers:
                    raise ValueError(
                        f"route {route_name!r} references unknown provider {target.provider!r}"
                    )
        return self


def load_gateway_config(path: Path) -> GatewayConfig:
    with path.open("rb") as handle:
        return GatewayConfig.model_validate(tomllib.load(handle))
