# ADR-005: Orchestration Approach (Deterministic Pipeline; Framework vs. Thin Core)

## Status

Proposed — 2026-11-07. **Not ready for acceptance:** the candidate frameworks were not researched (see Evidence gap).

## Context

The online path needs an orchestrator that runs retrieval, context assembly, generation and validation with deadlines, bounded retries, identity propagation and tracing (Ch. 7). Azure's RAG guidance distinguishes **standard RAG** (fixed sequence; the orchestrator does not decide whether, where or how often to search) from **agentic RAG** (agent treats retrieval as a tool), and names Microsoft Agent Framework, Semantic Kernel, Azure AI Agent service and LangChain as ways to implement an orchestrator [SRC-053]. Owner preferences: minimal packages, avoid premature abstraction, testability, ADR-driven.

## Requirements

Deterministic and replayable; every architectural contract unit-testable (filtering inside retrieval, cache isolation, prompt confinement, citation validation, bounded model calls — Ch. 7 §7.8); provider-agnostic (local + Azure OpenAI); OpenTelemetry-friendly; low dependency surface; room to add agentic control later.

## Options Considered

- A: **Thin custom orchestrator** with ports (Embedder, Retriever, LLM, Cache, Tracer).
- B: **Framework-based** (LangChain, Semantic Kernel, Agent Framework, LlamaIndex, DSPy). **Not researched.**
- C: **Managed agent service** (Foundry Agent Service prompt/hosted agents) [SRC-054]; couples to Azure; per-user conversation authorization is the application's job [SRC-054].

## Decision (proposed)

Use A for the reference implementation: a framework-free orchestrator behind ports, with the contracts of Ch. 7 enforced and mutation-tested. Allow B or C as *adapters at the edges* (e.g., a framework-provided retriever or tool runner) once researched, never as the owner of identity, filtering, caching or validation.

## Rationale

The contracts that matter most for safety are small, explicit and easy to test in a thin core (executed in `docs/exercises/ch07_orchestrator_contracts.py`, with five injected defects all detected). A framework adds abstraction layers between identity and the data tier, which is the opposite of what the security model wants unless proven otherwise. Fewer packages also matches the owner's preferences.

## Trade-offs

More code to own (retries, tracing, provider adapters); slower start than a framework; risk of reinventing features frameworks already ship. Mitigation: keep the core small, port-based, and replaceable.

## Consequences

Ch. 16–17 implement the core and adapters; evaluation harness calls the orchestrator directly (replayability). Agentic extensions (Ch. 15) wrap the same ports as tools.

## Security Considerations

Identity object immutable and passed to every stage; filters in data layer; prompt confinement is a mitigation not a boundary; deterministic output validation (OWASP LLM01 guidance [SRC-057]); model treated as untrusted.

## Performance and Cost

Thin core adds negligible overhead; no measurements yet. Framework overhead and token usage not evaluated.

## Evidence gap (blocks acceptance)

Research and compare at least: Semantic Kernel (.NET/Python), LangChain, LlamaIndex, Microsoft Agent Framework, DSPy — capabilities, maturity, versions, licenses, observability hooks, and how each handles per-request identity and retrieval filters.

## Reversal Conditions

A researched framework provides a needed capability (e.g., mature tool-calling loops, evaluation integration) with acceptable abstraction cost; team preference shifts to .NET/Semantic Kernel (relevant to the reader persona); Azure-managed agent service becomes mandated.

## References

SRC-053, SRC-054, SRC-057 (see RESEARCH-REGISTER).
