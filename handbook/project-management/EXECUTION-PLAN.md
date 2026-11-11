# Execution Plan

Date: 2026-11-07 · Governing rules: CLAUDE.md §2.4, §4, §5, §9.4, §15.

## Principles

- Bounded milestones; one coherent capability or 2–3 chapters at a time.
- Research → outline → author → review → integrate → gate (CLAUDE.md §5.1).
- PROGRESS.md updated after each batch; it is the source of truth.
- Handbook chapters reference implementation files rather than being their only copy.

## Milestone Sequence

| Milestone | Scope | Exit criteria |
|---|---|---|
| M0 | Structure, PRD, TOC, plan, progress, register, quality criteria, tech proposal | All M0 files exist; ADR-001 proposed |
| M1 | Research inventory, source verification, reference architecture, tech comparison, initial ADRs (001–004+), diagram inventory, implementation roadmap, version matrix | Tier-1 sources verified and registered; ADR-001 accepted or revised |
| M2 | Ch. 1–5 (B1–B3) | Completion gate per chapter |
| M3 | Ch. 6–9 (B4–B5) | same |
| M4 | Ch. 10–15 (B6–B8) | same |
| M5 | Reference implementation (20 steps in CLAUDE.md §4) + Ch. 16–17 | Each step tested before the next |
| M6 | Ch. 18–23, production hardening, readiness checklist | Tests executed; QUALITY-REPORT updated |
| M7 | Ch. 24–29 | Gate per chapter |
| M8 | Ch. 30–33, cheat sheets, flashcards, mocks | 100+ Qs, 15–25 scenarios |
| M9 | Integration, validation scripts, PDF, final reports | CLAUDE.md §18 gates |

Sequencing note: M5 (implementation) is deliberately placed before Part V–VII chapters so that evaluation, observability and security chapters can cite measured, executed behaviour. Part IV chapters (16–17) are written alongside the implementation, not before.

## Batch Plan (handbook)

B1 Ch1–2 · B2 Ch3–4 · B3 Ch5 (+ ADR-002/003 finalization) · B4 Ch6–7 · B5 Ch8–9 · B6 Ch10–11 · B7 Ch12–13 · B8 Ch14–15 · B9 Ch18–19 · B10 Ch20–21 · B11 Ch22–23 · B12 Ch24–25 · B13 Ch26–27 · B14 Ch28–29 · B15 Ch30–31 · B16 Ch32–33.

## Tooling Plan (to be built in M1/M9)

- `scripts/build-handbook`: deterministic concatenation of `docs/chapters/*.md` into the canonical handbook.
- `scripts/validate-docs`: required sections, references present, no placeholder markers.
- `scripts/validate-links`: internal and external link checks.
- `scripts/validate-diagrams`: Mermaid rendering check (tool availability to be verified).
- PDF: toolchain to be selected and verified in M1 (see OPEN-ISSUES OI-003).

## Per-Batch Checklist

1. Read PROGRESS.md, TOC, relevant ADRs; check status.
2. Research; register sources (RESEARCH-REGISTER).
3. Outline.
4. Author complete chapters with diagrams, code (verified or marked illustrative), interview Qs, exercises, references.
5. Technical review.
6. Integrate (handbook, glossary, references, progress, open issues).
7. Completion gate.
