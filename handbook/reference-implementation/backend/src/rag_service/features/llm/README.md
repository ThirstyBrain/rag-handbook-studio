# LLM gateway: how to use it

**One rule: application code never imports a vendor SDK and never names a model.** It asks the gateway for a *route* (a purpose such as `answer`, `rewrite`, `judge`, `embed`). Configuration maps each route to an ordered chain of `(provider, model)` targets. Swap Claude for a local model, add Grok as a fallback, or change a model version by editing a TOML file, not code.

```
feature code ──► LlmGateway ──► route "answer": [ local/llama… → claude/… → openai/… ]
                    │            retries · timeout · fallback · circuit breaker · token cap
                    │            data-sensitivity policy · spend budget · cost estimate · events
                    └──► provider adapters: openai_compat (OpenAI, Grok, Ollama, vLLM) · anthropic (official SDK) · fake
```

## 1. Configure

Copy `reference-implementation/config/llm-gateway.example.toml` to `llm-gateway.toml`, set real model ids, and point the app at it:

```bash
export RAG_LLM_CONFIG_FILE=config/llm-gateway.toml
export ANTHROPIC_API_KEY=...        # only the providers you use; keys are read from the environment, never from the file
```

Key concepts in the file:

| Concept | Meaning |
|---|---|
| `providers.<name>` | `kind` = `anthropic` / `openai_compat` / `fake`; `locality` = `local` or `external`; `base_url`; `api_key_env` (the *name* of an environment variable) |
| `routes.<name>` | `kind` = `chat` or `embed`; `chain` = ordered targets (put local and cheap first: that is the fallback order); `timeout_s`, `max_attempts_per_target`, `max_output_tokens` (hard cap), `max_batch` |
| `embedding_space` | On every target of an `embed` route. All targets must share it, because vectors from different models cannot be mixed in one index. The file is rejected otherwise. |
| `prices."provider/model"` | Optional USD per million tokens, supplied by you. No prices ship with the repository. |
| `external_daily_budget_usd` | Optional cap on external spend per UTC day. Needs prices for external models; an unpriced external model is not used while a budget is set. |
| `strict` | `true`: refuse to start if a route has no usable provider. Use in production. |

Without `RAG_LLM_CONFIG_FILE` there is no gateway and any feature asking for it gets `503 llm_not_configured`.

## 2. Call it from a feature

```python
from typing import Annotated
from fastapi import Depends
from rag_service.features.llm import ChatRequest, LlmGateway, Message, Sensitivity
from rag_service.features.llm.deps import get_llm_gateway


async def answer(question: str, llm: Annotated[LlmGateway, Depends(get_llm_gateway)]) -> str:
    result = await llm.chat(
        ChatRequest(
            route="answer",
            system="Answer only from the provided context.",
            messages=[Message(role="user", content=question)],
            max_output_tokens=800,
            sensitivity=Sensitivity.INTERNAL,
        )
    )
    return result.text  # also: result.usage, .provider, .model, .fallback_used, .estimated_cost_usd
```

Streaming (retry/fallback happen only *before the first token*; a failure after text has been sent is raised to you):

```python
async for event in llm.stream(request):
    if isinstance(event, TextDelta):
        send_to_client(event.text)
    elif isinstance(event, StreamEnd):
        record(event.result.usage)
```

Embeddings (one model per index; the result tells you the space and dimensions):

```python
emb = await llm.embed(EmbedRequest(route="embed", inputs=chunks))
emb.vectors, emb.dimensions, emb.embedding_space
```

## 3. Data sensitivity is enforced here, not in prompts

`Sensitivity.RESTRICTED` requests are only ever sent to providers with `locality = "local"`. If a route has none, the gateway raises `PolicyViolation` (HTTP 403 `llm_policy_violation`): it **fails closed** and never falls back to an external provider. Set the sensitivity from your document classification (Chapter 8) when you build the request.

## 4. Errors

| Exception | Meaning | Retried | Next target |
|---|---|---|---|
| `RateLimited`, `ProviderUnavailable`, `ProviderTimeout` | transient | yes (bounded, with backoff; honours Retry-After up to the cap) | yes |
| `ProviderAuthError`, `TargetUnsupported` | bad key; unknown model or no such operation | no | yes |
| `InvalidRequest` | the request or route is wrong | no | no |
| `ContentRefused` | the provider declined for safety | no | no (not shopped around) |
| `PolicyViolation`, `BudgetExceeded` | no allowed target | n/a | n/a |
| `AllTargetsFailed` | every target failed; `.attempts` lists `(provider, model, error class)` | | |

In a FastAPI app these map to safe problem responses automatically (`features/llm/http.py`): no provider name, model or message text reaches the client. Error messages never contain prompts or provider response bodies.

## 5. What the gateway does for you

Timeouts per route; bounded retries with exponential backoff and jitter; fallback down the chain; a **circuit breaker** per provider (opens after N consecutive failures, one trial call after the reset window); a hard **output-token cap** per route; `temperature` is dropped for providers that reject it (current Claude models do); **cost estimation** from your prices; an optional **external spend budget**; and a content-free `llm.call` event per call (route, provider, model, tokens, latency, attempts, fallback flag, cost, outcome). `gateway.status()` returns provider availability and breaker state.

## 6. Testing without a model

Use `kind = "fake"` in a test config (refused automatically when `RAG_ENVIRONMENT=production`), or construct `FakeProvider("name", outcomes=[...])` and pass it to `LlmGateway(config, {"name": provider})`. Outcomes are consumed per call: a string becomes the reply, an `LlmError` is raised, so retry and fallback paths are testable with no network. See `tests/unit/test_llm_gateway.py`.

Other test levels in the repository: adapters against mocked HTTP (`tests/unit/test_llm_adapters.py`), a real local Ollama server (`tests/integration/test_llm_ollama.py`, skipped if Ollama is down), and an optional live Claude call (`tests/integration/test_llm_live.py`, skipped unless you opt in and supply a key; it costs a few tokens).

## 7. Adding a provider

Implement the `LlmProvider` protocol in `ports.py` (`chat`, `stream`, `embed`, `aclose`, plus the capability flags), map the vendor's errors to the taxonomy in `errors.py` **without copying vendor messages**, register the `kind` in `build_providers` (`gateway.py`) and in `config.py`. Most OpenAI-compatible servers need no code: add a provider block with `kind = "openai_compat"` and a `base_url`.

## 8. Known limits

- **Verified**: the Ollama path against a real server; the Claude path against the official SDK with a mocked transport (headers, body, parsing, errors, streaming). **Not verified**: a live call to Claude, OpenAI or Grok in this repository (no keys were available). The OpenAI and xAI wire formats are *unverified against their vendor documentation* (OpenAI's reference page returned HTTP 403; the xAI page documents `/v1/responses`, not chat completions). Treat those two as experimental until you run the optional live test.
- Spend accounting is in memory and per process; restarts reset it and concurrent calls can overshoot a budget slightly.
- Streaming cannot switch provider after the first token.
- Claude: thinking tokens count toward `max_tokens`; give Claude routes a generous `max_output_tokens`. `temperature` is never sent.
- No embeddings for Claude (no such API); use a different provider for `embed` routes. The locally installed Ollama models returned 501 for embeddings, so pull an embedding model before using a local `embed` route.
- No tool calling or structured-output abstraction yet; add it when a component needs it (agentic RAG, Chapter 15).
