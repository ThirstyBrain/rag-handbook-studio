"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rag_service.features.llm import GatewayConfig, load_gateway_config

EXAMPLE = Path(__file__).resolve().parents[2] / "config" / "llm-gateway.example.toml"


def test_example_config_loads_and_contains_no_secrets() -> None:
    cfg = load_gateway_config(EXAMPLE)
    assert set(cfg.providers) == {"local", "claude", "openai", "grok"}
    assert {r for r, c in cfg.routes.items() if c.kind == "embed"} == {"embed"}
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "sk-" not in text and "Bearer" not in text
    # secrets are referenced by environment-variable name only
    assert all(
        (p.api_key_env or "").isupper() or p.api_key_env is None for p in cfg.providers.values()
    )


def test_unknown_keys_and_unknown_provider_references_are_rejected() -> None:
    base = {
        "providers": {"p": {"kind": "fake", "locality": "local"}},
        "routes": {"r": {"chain": [{"provider": "p", "model": "m"}]}},
    }
    GatewayConfig.model_validate(base)
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate({**base, "surprise": 1})
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate(
            {**base, "routes": {"r": {"chain": [{"provider": "ghost", "model": "m"}]}}}
        )
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate(
            {**base, "providers": {"p": {"kind": "fake", "locality": "elsewhere"}}}
        )
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate({**base, "routes": {"r": {"chain": []}}})
    with pytest.raises(ValidationError):
        GatewayConfig.model_validate(
            {
                **base,
                "routes": {
                    "r": {"chain": [{"provider": "p", "model": "m"}], "max_attempts_per_target": 0}
                },
            }
        )
