# ADR-018: Evaluation Policy

## Status

Proposed — 2026-11-09. Written during the Chapter 18 research batch; to be accepted (or revised) before component 17 is built. Nothing described here is implemented; the measurement machinery was exercised only on constructed data (`docs/exercises/ch18_evaluation.py`, 13/13 injected defects detected).

## Context

CLAUDE.md §12 requires separate retrieval and generation evaluation, a versioned golden dataset, and regression evaluation after any change to chunking, embeddings, retrieval, reranking, prompts, models or context assembly, without optimising one metric at the expense of the system. The reference implementation will need these before its quality claims mean anything.

## Requirements

Comparable results across runs; protection against silent regression including in small segments; a judge whose reliability is known before it gates a release; evaluation that respects tenant isolation and permissions; the golden set treated as sensitive data; low enough cost to run on every meaningful change.

## Options Considered

- **A. Aggregate-score gate on a fixed benchmark.** Simple. Rejected: noise-blind and hides segment regressions.
- **B. Human review only.** Highest trust; does not scale to every change.
- **C. Paired-interval gate over a versioned golden set with validated judges, per-slice reporting and permission-aware runs (selected).**
- **D. Fully reference-free LLM-judged evaluation without human calibration.** Cheapest. Rejected: judge bias is documented and unquantified for our domain until calibrated against human labels.

## Decision

1. Retrieval, generation and system metrics are reported separately. Retrieval: Recall@K (K equals the number of chunks given to the generator) and nDCG@K, with MRR for lookup slices. Generation: faithfulness (supported claims over claims), citation accuracy split into phantom, unsupported and uncited, abstention precision and recall. System: latency, time to first token, cost per query, error rate, security violations.
2. The golden set is versioned, split into development and held-out parts, and keys relevance to **document plus locator**, never to chunk ids. Each case carries an identity, an answerable flag, graded relevance, atomic reference facts, slice tags and provenance. Unanswerable, cross-tenant and hostile-document cases are mandatory.
3. Runs execute the real pipeline as each case's identity.
4. Comparisons use a paired bootstrap over queries and return `regression | inconclusive | improvement` per metric and per declared critical slice. "Inconclusive" never counts as a pass. Accepted regressions are recorded with an owner and an expiry.
5. A judge is accepted only after calibration against a stratified human-labelled sample reporting raw agreement and Cohen's kappa per slice and an order-swap test for pairwise judgments. Judge model, prompt and settings are pinned and versioned; a change restarts validation. Judges for restricted data run on local providers via the gateway sensitivity policy.
6. Cheap deterministic metrics run on every pull request; the full suite with judges runs on release candidates and nightly; production is sampled online with the same judges (Chapter 19).
7. The golden set and evaluation results are stored with the access control of the most sensitive source they reference.

## Rationale

The executed exercise showed the failure modes the policy prevents: a recall denominator that silently turns recall into precision, an aggregate that improves while one slice falls from 0.70 to 0.40, a constant judge with 90% agreement and kappa 0, a position-biased judge that prefers the first answer 75% of the time, and a gate that cannot see a 3-point regression at 30 cases (flagged 20% of the time) but sees it at 400 (98%) under the simulation's assumptions.

## Trade-offs

More upfront work (labelled calibration data, a sizeable golden set) and a gate that often says "inconclusive". Per-slice gating invites multiple-comparison false positives, so the list of gating slices is pre-registered. The golden set becomes a sensitive asset to protect.

## Consequences

Component 17 builds the runner, scorer, store and gate to this policy. Component 11 and 12 must emit the structured outputs the metrics need (retrieved chunk ids with document ids and locators, claims, citations, abstention flag). Chapter 19's online sampling reuses the same judges.

## Security Considerations

Judges read untrusted retrieved text and must be treated as injectable: constrained output schema, validated, deterministic checks first, no verdict ever authorises an action. External judges receive chunk text; the sensitivity policy applies. Evaluation identities must not bypass row-level security.

## Performance and Cost

Not measured. Cost is dominated by judge tokens and generation per case per run; levers are caching verdicts by (judge version, case, answer hash, context hash), sampling online traffic and deterministic pre-filters. No prices asserted.

## Reversal Conditions

Revisit when labelled production data supports a domain-trained judge (ARES-style), when a gated metric stops tracking user outcomes, when golden-set size makes per-change runs impractical, or when the pre-registered slice list produces persistent false alarms.

## Evidence gaps

No real judge, golden set or RAG pipeline has been evaluated. ARES and Ragas were read at abstract and documentation level and not run. The incomplete-judgment (pooling) problem and the Wilson interval are stated from general knowledge, not from a reviewed source.

## References

SRC-063, SRC-064, SRC-132 to SRC-135, SRC-139 to SRC-141, SRC-142. Chapter 18. ADR-012, ADR-017.
