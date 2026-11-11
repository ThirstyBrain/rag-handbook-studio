"""The gateway is built from settings, injected into features, and closed on shutdown."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI

from rag_service.core.config import Settings
from rag_service.features.llm import ChatRequest, LlmGateway, Message
from rag_service.features.llm.deps import get_llm_gateway
from rag_service.main import create_app
from tests_types import ClientFor

TOML = """
[providers.dev]
kind = "fake"
locality = "local"

[routes.answer]
chain = [{ provider = "dev", model = "fake-model" }]
"""


def app_with(tmp_path: Path, environment: str) -> FastAPI:
    path = tmp_path / "llm.toml"
    path.write_text(TOML, encoding="utf-8")
    app = create_app(
        Settings(_env_file=None, environment=environment, llm_config_file=path),  # type: ignore[call-arg,arg-type]
        configure_logs=False,
    )

    @app.post("/_ask")
    async def ask(llm: Annotated[LlmGateway, Depends(get_llm_gateway)]) -> dict[str, str]:
        result = await llm.chat(
            ChatRequest(route="answer", messages=[Message(role="user", content="hi")])
        )
        return {"provider": result.provider, "model": result.model}

    return app


async def test_feature_uses_gateway_from_settings(tmp_path: Path, client_for: ClientFor) -> None:
    app = app_with(tmp_path, "test")
    response = await client_for(app).post("/_ask")
    assert response.status_code == 200 and response.json() == {
        "provider": "dev",
        "model": "fake-model",
    }


async def test_fake_provider_is_refused_in_production(
    tmp_path: Path, client_for: ClientFor
) -> None:
    app = app_with(tmp_path, "production")
    response = await client_for(app).post("/_ask")
    assert response.status_code == 503 and response.json()["code"] == "llm_unavailable"
    assert "dev" not in response.text and "fake-model" not in response.text
    gateway = app.state.llm_gateway
    assert gateway.status()["dev"]["available"] is False


async def test_missing_gateway_gives_clear_503(make_app, client_for: ClientFor) -> None:  # type: ignore[no-untyped-def]
    app = make_app()

    @app.post("/_ask")
    async def ask(llm: Annotated[LlmGateway, Depends(get_llm_gateway)]) -> dict[str, str]:
        return {}

    response = await client_for(app).post("/_ask")
    assert response.status_code == 503 and response.json()["code"] == "llm_not_configured"


async def test_gateway_is_closed_on_shutdown(tmp_path: Path) -> None:
    app = app_with(tmp_path, "test")
    closed = {"n": 0}
    gateway = app.state.llm_gateway
    original = gateway.aclose

    async def spy() -> None:
        closed["n"] += 1
        await original()

    gateway.aclose = spy
    async with app.router.lifespan_context(app):
        pass
    assert closed["n"] == 1


async def test_gateway_errors_map_to_safe_problem_responses(
    make_app,
    client_for: ClientFor,  # type: ignore[no-untyped-def]
) -> None:
    from rag_service.features.llm import ContentRefused, InvalidRequest, PolicyViolation
    from rag_service.features.llm.errors import BudgetExceeded, ProviderAuthError

    app = make_app()
    cases = {
        "policy": (PolicyViolation("secret-provider-detail"), 403, "llm_policy_violation"),
        "budget": (BudgetExceeded("secret-provider-detail"), 503, "llm_budget_exceeded"),
        "refused": (ContentRefused("secret-provider-detail"), 422, "llm_refused"),
        "invalid": (InvalidRequest("secret-provider-detail"), 500, "llm_invalid_request"),
        "other": (ProviderAuthError("secret-provider-detail"), 502, "llm_error"),
    }
    for name, (exc, _, _) in cases.items():
        app.add_api_route(f"/_{name}", _raiser(exc), methods=["GET"])
    client = client_for(app)
    for name, (_, status, code) in cases.items():
        response = await client.get(f"/_{name}")
        assert response.status_code == status and response.json()["code"] == code
        assert "secret-provider-detail" not in response.text


def _raiser(exc: Exception):  # type: ignore[no-untyped-def]
    async def endpoint() -> None:
        raise exc

    return endpoint


@pytest.mark.parametrize("bad", ["not = [valid", "[providers.x]\nkind='nope'\nlocality='local'"])
def test_invalid_config_file_fails_fast_at_startup(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(Exception):  # noqa: B017 - TOML or validation error, both must stop startup
        create_app(Settings(_env_file=None, llm_config_file=path), configure_logs=False)  # type: ignore[call-arg]
