# ADR-007: Query Transformation and Multi-Step Retrieval Policy

## Status

Proposed — 2026-11-07. Evidence from Chapters 10–11 research (SRC-055, 080–093, mostly abstract-level) and executed stand-in demonstrations (no real language model). Must be validated against the M5 golden dataset with a real model before acceptance.

## Context

Query-time model calls (rewriting, expansion, HyDE, decomposition, multi-query, iteration) can close query–document gaps but add latency, cost, security surface and new failure modes. Evidence reviewed: expansion gains correlate negatively with retriever strength and can turn negative for strong retrievers [SRC-084]; fan-out has a documented off-topic failure mode [SRC-087]; many multi-hop benchmarks can be solved by shortcuts [SRC-090]; iterative and graph methods report large gains on multi-hop QA in the authors' own evaluations [SRC-089, SRC-091].

## Requirements

Measurable benefit per query class; bounded latency and cost per request; no ability for model output to alter authorization; graceful degradation to the untransformed query; auditability of what was transformed; testability without a model.

## Options Considered

- **A: No query transformation** beyond deterministic normalisation.
- **B: Always-on LLM rewrite/expansion** for every query.
- **C: Gated, per-class policy** (this ADR's decision).
- **D: Fully agentic retrieval** (Chapter 15).

## Decision (proposed)

Adopt **C** with these rules:

1. **Normalisation always**, identical to chunk cleaning [SRC-055].
2. **Original query always participates** in the retrieval/fusion set; every LLM transform has a **deadline and a fallback** to the untransformed query.
3. **Filters derive from the identity object only**; model output never sets or widens filters (ADR-006). The rewriter and reader are treated as untrusted-input processors [SRC-057].
4. **Gate** transforms: deterministic checks first (follow-up detection, identifier patterns, conjunction/length heuristics), a small trained router second [SRC-085]. Identifier-like queries bypass rewriting.
5. **Glossary expansion first** for stable vocabulary gaps; **LLM expansion/HyDE** only as flag-gated experiments with down-weighted terms, evaluated against the hybrid + rerank baseline [SRC-084].
6. **Conversational rewrite** only for context-dependent follow-ups, bounded history, original turn retained, topic-switch tests required [SRC-093].
7. **Multi-query fan-out**: capped variants, similarity-gated, deduplicated, original weighted, reranker after fusion [SRC-087, SRC-067].
8. **Iterative multi-hop** only for dependent multi-hop classes confirmed on a **shortcut-free** evaluation set [SRC-090]; mandatory guards: visited set, hop cap, time/token budget, recorded stop reason, per-hop identity filters.
9. **Graph retrieval**: not in the default path; evaluate if relational/global questions dominate; nodes/edges carry provenance and ACLs (ADR-006).
10. Per-request and per-tenant budgets (LLM calls, variants, hops, tokens); stop-reason and transform-effect metrics are required telemetry.

## Rationale

The only quantified failure evidence points against blanket use of expansion on strong retrievers [SRC-084]; routing avoids paying multi-step cost for simple queries [SRC-085]; guarded loops and shortcut-free evaluation address the documented failure modes of iteration and benchmarks [SRC-090]. The executed demos (stand-in steps) confirmed the mechanics: contamination on topic switches, expansion drift (and its mitigation by down-weighting), consensus bias and drift in fan-out, cycle termination.

## Trade-offs

Gating and evaluation add engineering work and a router dependency; conservative defaults may leave recall gains unclaimed until measured; multi-step paths add latency variance; keeping the original query and fallbacks limits the upside of a very good transform.

## Consequences

`QueryTransformer` and loop controller ports in M5; golden dataset must include follow-up, topic-switch, vocabulary-gap, identifier, compound and shortcut-free multi-hop classes; evaluation compares each transform against baseline per class; telemetry records transform type, duration, result-change flag, stop reason, token cost.

## Security Considerations

Rewriter/reader read untrusted text; outputs are validated and never used for authorization; bridge entities are sanitised; per-hop identity filters; graph ACLs; cost-abuse controls (budgets, rate limits); logging by hash.

## Performance and Cost

Transforms add sequential model latency before retrieval; fan-out latency is the max of legs; iteration latency is the sum of hops (executed with assumed unit costs only). No measurements yet; token and latency costs to be measured in M5/M6.

## Reversal Conditions

Measured per-class gains justify broader use (for example a weaker retriever mix) or a transform never changes results (delete it); router accuracy is too low; stop-reason telemetry shows frequent `max_hops`; graph maintenance cost exceeds benefit; agentic control (Chapter 15) outperforms deterministic loops within budget.

## Evidence gaps

All LLM-dependent behaviour is unmeasured here (stand-ins only); 14 papers read at abstract level (OI-011); no router evaluation; no embedding-similarity variant gate tested; local-model option for rewriting (Ollama) not evaluated (OI-040, OI-041).

## References

SRC-055, 057, 067, 080–093 (see RESEARCH-REGISTER).
