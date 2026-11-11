# ADR-012: Provider-Neutral LLM Gateway

## Status

Accepted — 2026-11-08 (implemented and verified against a local model and mocked vendor transports; a live call to Claude, OpenAI and Grok has not been run: OI-049).

## Context

The reference implementation must call language models and embedding models from several features (query transformation, generation, evaluation judging, embeddings) and must work with Claude, OpenAI, Grok and local models, chosen by cost, privacy and availability. Owner principles: cost first, fallback models, local before cloud, minimal packages. The handbook's earlier chapters raised the same needs: data egress to external services (Chapter 12), per-route model choice (ADR-007, ADR-008), embedding model lock-in (ADR-002), agent budgets (ADR-010).

## Requirements

Application code independent of vendors and model names; config-driven routing with ordered fallback; timeouts, bounded retries, circuit breaking; token caps and optional spend budgets; a data-sensitivity policy that fails closed; no prompts, responses or keys in logs, events or errors; embedding vectors never mixed across models; testable offline; works with the official Claude SDK.

## Options Considered

- **A: Call each vendor SDK directly from features.** Simple, but couples code to vendors and duplicates retry, cost and policy logic.
- **B: Adopt a third-party gateway/proxy library or service (for example LiteLLM or an API-management gateway).** Not researched in this repository; adds a dependency or a deployment, and its policy features were not verified here.
- **C: A small in-process gateway with a provider port and adapters (this ADR).**
- **D: Only OpenAI-compatible endpoints for everything (including Claude through a compatibility layer).** One protocol, but the Claude SDK guidance is to call Claude through the official SDK, not through compatibility shims.

## Decision

Option **C**.

1. **Port and adapters.** `LlmProvider` protocol; adapters: `openai_compat` (plain `httpx`; covers OpenAI, xAI Grok, Ollama, vLLM), `anthropic` (official `anthropic` SDK, imported lazily, SDK retries disabled), `fake` (deterministic, refused in production).
2. **Routes, not models.** Callers name a route; a TOML file maps routes to ordered `(provider, model)` chains. Model ids, base URLs and optional prices live only in that file; secrets are referenced by environment-variable name.
3. **Uniform policy in the gateway:** per-route timeout; bounded retries with exponential backoff, jitter and Retry-After (capped); fallback down the chain for transient, auth and target-unsupported errors; **no retry and no fallback** for invalid requests and for provider refusals; per-provider circuit breaker with a single half-open probe; per-route output-token cap; `temperature` dropped for providers that reject it.
4. **Sensitivity policy:** `restricted` requests are sent only to `locality = "local"` providers and otherwise fail with `PolicyViolation` (never fall back to external).
5. **Cost controls:** operator-supplied prices; estimated cost per call; optional per-UTC-day external budget; an unpriced external model is not used while a budget is set; budget state is in memory (best effort).
6. **Embeddings:** every target of an `embed` route must declare the same `embedding_space` (config validation); inconsistent vector dimensions are rejected.
7. **Observability without content:** one `llm.call` event per call (route, provider, model, tokens, latency, attempts, fallback, cost, outcome); errors carry class names only.
8. **Streaming:** retry/fallback only before the first token.
9. **Wiring:** `Settings.llm_config_file`; `create_app` builds the gateway (strict mode available), stores it on `app.state`, closes it on shutdown; features obtain it through `get_llm_gateway`; gateway errors map to safe problem responses.

## Rationale

Executed evidence: 15 of 15 injected policy defects were detected by the tests (restricted data to external providers, token cap, temperature stripping, retry of invalid requests, breaker threshold, budget, Retry-After cap, mid-stream fallback, unpriced spend, spend recording, batch limit, mixed spaces, unsupported-target mapping, refusal handling); a real local Ollama server exercised chat, streaming with usage, clamping, fallback from a dead endpoint, and fallback from an unsupported embedding model (HTTP 501); the Claude adapter was validated against the installed SDK, which showed that the SDK sends the key as a bearer token (not `x-api-key`) and an `anthropic-version` of 2026-10-21, contrary to my assumption, and that Claude requests must not carry `temperature`.

## Trade-offs

We own a small amount of retry/breaker/budget code instead of reusing a library; Claude and the OpenAI-compatible path have different features, so the common interface is the lowest common denominator (no tool calling, structured output or provider-specific caching controls yet); budget accounting is per process; adapters must be maintained as APIs change; `anthropic` brings in `httpx2` next to `httpx` (two HTTP stacks).

## Consequences

Features depend on `LlmGateway` only. Evaluation and query-transformation code can finally run against real local or hosted models by changing configuration. New providers are an adapter plus a `kind`. Production deployments must set `strict = true`, provide keys through the platform's secret store, and decide which routes may use external providers.

## Security Considerations

No keys in config or logs (environment-variable references; SDK and httpx error messages are never copied); exception text and events carry no prompt or response content; restricted data fails closed; external providers are sub-processors whose terms were not reviewed (OI-049); the `fake` provider is blocked in production; spend and rate controls bound cost-abuse; provider base URLs come from trusted configuration only (never from requests).

## Performance and Cost

Overhead is one in-process dispatch plus the provider call. Observed once on the dev host with a 0.5B local model: a chat call took about 440 ms (single sample, not a benchmark). Cost depends entirely on operator-supplied prices; none are shipped.

## Reversal Conditions

Adopt an external gateway if its verified policy features (sensitivity routing, budgets, audit) outweigh the added dependency; split out tool-calling and structured-output abstractions when agentic RAG (ADR-010) is implemented; move budget state to shared storage when running several replicas.

## Evidence gaps

No live call to Claude, OpenAI or Grok; OpenAI chat-completions and xAI chat-completions formats unverified against vendor docs; no concurrency or load test; no measurement of retry/breaker behaviour against real rate limiting; third-party gateway options not researched; vendor data-processing terms not reviewed.

## References

SRC-118 (Ollama OpenAI compatibility), SRC-119 (xAI API reference, partial), SRC-120 (Anthropic SDK documentation as provided with the claude-api skill), RFC 9457 (SRC-117), ADR-002, ADR-007, ADR-008, ADR-010.
