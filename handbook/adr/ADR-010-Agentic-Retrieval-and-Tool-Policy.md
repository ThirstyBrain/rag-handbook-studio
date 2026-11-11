# ADR-010: Agentic Retrieval and Tool Policy

## Status

Proposed — 2026-11-08. Evidence from Chapter 15 research (SRC-057, 085, 089, 092, 110–116, mostly abstract- and documentation-level) and an executed harness with a scripted policy (no language model; OI-046). Must be validated with a real model and an adversarial trajectory suite before acceptance.

## Context

Letting a model choose retrieval and tool actions can serve open-ended tasks that fixed pipelines cannot, but adds latency, cost, non-determinism and the risk of Excessive Agency [SRC-113]. Vendor guidance recommends the simplest solution that works and notes agents cost more and add latency [SRC-115]. Managed agentic retrieval exists with GA and preview parts [SRC-114]; MCP standardises tool discovery and invocation but leaves trust to implementers [SRC-116].

## Requirements

No model output may set identity, widen authorization or cause an unapproved side effect; bounded cost, steps and time; auditable trajectories; graceful abstention; testable without a model; adversarial robustness measured, not assumed.

## Options Considered

- **A: No agentic mode** (fixed pipeline + routing + guarded iteration, ADR-007).
- **B: Custom loop with a code-owned tool layer** (this ADR's decision for agentic tasks).
- **C: Managed agentic retrieval** (Azure AI Search knowledge bases) [SRC-114].
- **D: Model-trained self-reflection** (Self-RAG-style) [SRC-111].
- **E: Open-ended agent with broad tools** (rejected).

## Decision (proposed)

1. **Default is A.** Agentic mode is enabled per task type, only where measured failure classes cannot be handled by routing and guarded iteration.
2. Agentic mode uses **B** behind the following non-negotiable controls (executed in the Ch. 15 harness): per-request tool **allow-list**; tool schemas with **no identity arguments**, unknown arguments rejected; identity **injected by the harness**; downstream authorization re-checked; **approval and recipient/domain policy** for any side-effect tool; **step, token, cost and deadline budgets** and repeated-call detection with recorded stop reasons; observations treated as **untrusted** and length-limited; **audit by hash**, not raw text.
3. Retrieval tools are thin wrappers over the same orchestrator retrieval path (ADR-004, ADR-006, ADR-009); a `fetch_document` tool re-authorizes every call.
4. Outbound/side-effect tools are **off by default**; enabling one requires an ADR note, an owner, a policy and tests.
5. An **evaluator gate** (CRAG-style) chooses answer / re-query / abstain; thresholds are calibrated on answerable and unanswerable queries per retriever and reranker (ADR-008).
6. **C** is evaluated when the platform is Azure AI Search and GA capabilities (the `2026-04-01` API, minimal extractive retrieval) suffice; preview features (LLM planning, answer synthesis) are not used in production until GA [SRC-114].
7. **MCP** may be used for tool exposure only with the same controls at server and client; tool annotations are untrusted [SRC-116].
8. Evaluation includes trajectory metrics, repeated runs for variance, and an adversarial suite (injection, tenant-override, loop-inducing, exfiltration) in every regression run.

## Rationale

The only mechanical evidence here is that the harness controls hold regardless of model behaviour, and that independent layers back each other up (single-layer removal was masked, paired removal caught). The literature supports agentic patterns on benchmarks (abstract-level) but does not remove the cost and risk, which is why autonomy is the last rung.

## Trade-offs

Controls add engineering work and reduce flexibility; approval adds friction; conservative defaults may leave capability unused; managed services trade control for speed; evaluation of non-deterministic agents is costlier.

## Consequences

Tool registry with side-effect classes; harness module; trajectory logging and metrics; adversarial test suite; per-task budgets; approval workflow; new golden-set classes (open-ended tasks, unanswerable, injected).

## Security Considerations

Prompt is not a security boundary; least privilege and per-user credentials; outbound channels gated; MCP servers treated as third-party code; logging without sensitive text; cost-abuse limits.

## Performance and Cost

Latency is the sum of sequential steps; cost grows with steps × accumulated context unless truncated. No measurements yet; Azure's published estimate uses hypothetical prices (illustrative method only).

## Reversal Conditions

Trajectory success does not beat the guarded workflow at comparable cost; incident or denied-call rates indicate unsafe behaviour; preview APIs change incompatibly; per-task cost exceeds value; a managed service provides equivalent controls with acceptable data posture.

## Evidence gaps

No real model run (OI-046); papers abstract-level; no adversarial benchmark executed; MCP spec page revision 2026-07-28 only; Azure feature split may change.

## References

SRC-057, 085, 089, 092, 110–116 (see RESEARCH-REGISTER).
