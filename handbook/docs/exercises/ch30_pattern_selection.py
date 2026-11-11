"""Chapter 30 exercise: choosing a RAG architecture pattern from requirements (stdlib only).

Chapter 30 is a catalogue (naive/advanced/modular RAG, long-context stuffing, routing between them, hierarchical
summary trees, entity graphs, agentic loops, text-to-SQL). A catalogue helps only if you can say WHEN each applies and,
as importantly, when it must NOT be adopted. This file encodes that judgement as an explicit, testable procedure:

  A. select_patterns(requirements) -> ordered recommendations, each with reasons and warnings, never a bare name;
  B. a cost model for "put the corpus in the prompt" vs retrieve vs route (retrieve first, fall back to the long prompt),
     with the break-even fraction derived analytically and tested;
  C. twelve constructed requirement sets with expected outcomes, and invariants that must hold for ALL inputs
     (swept over a grid): the baseline is always present, every recommendation has a reason, nothing advanced is
     recommended without an evaluation set, permission-sensitive corpora never get a cross-document summary index
     without a warning, adding a requirement never removes the baseline;
  D. a mutation check: each rule can be disabled and the tests must notice.

Run: python -I docs/exercises/ch30_pattern_selection.py [--mutants]
WHAT THIS IS NOT: the rules are MY engineering judgement built from the sources in the chapter (S207, S210-S214), not a
validated model of what works best. The thresholds (for example 0.5 of the context window, 3 s for iterative
retrieval) are ASSUMPTIONS [A]. Prices are abstract units [I] (one input token = 1.0 unit), so only RATIOS are
meaningful. The quality side of the routing trade-off (does the cheaper path answer as well?) is NOT modelled: the
authors of the routing paper report it for their models and data (S211), and nothing here measures it.
"""
from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass, field

MUT: set[str] = set()

# Assumptions [A], named so the chapter can discuss each.
LC_FILL_LIMIT = 0.5          # use at most half the window for the corpus: leaves room for instructions, answer, history
ITERATIVE_LATENCY_MS = 3000  # below this budget, iterate-retrieve-iterate is unrealistic with typical model latency
LC_MAX_QPD = 5_000           # queries/day above which stuffing a big prompt per query is rarely sensible [A]

LOOKUP, MULTI_HOP, GLOBAL, STRUCTURED = "lookup", "multi_hop", "global_summary", "structured_data"
QUERY_TYPES = {LOOKUP, MULTI_HOP, GLOBAL, STRUCTURED}


@dataclass(frozen=True)
class Requirements:
    corpus_tokens: int
    context_window: int
    query_types: frozenset[str] = frozenset({LOOKUP})
    permission_sensitive: bool = False   # documents have different ACLs
    update_rate: str = "slow"            # static | slow | fast
    latency_budget_ms: int = 8000
    queries_per_day: int = 1000
    has_eval_set: bool = True


@dataclass(frozen=True)
class Rec:
    pattern: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def select_patterns(r: Requirements) -> list[Rec]:
    recs: list[Rec] = []
    # 1. The baseline is always present: hybrid retrieval with permission filtering where needed, then evaluate it.
    base_reasons = ["every system needs a measured retrieval baseline before anything else is justified (Ch. 18)"]
    base_warn: list[str] = []
    if r.permission_sensitive:
        base_reasons.append("documents have different ACLs: filter by permission inside the query (Ch. 22)")
    if "baseline-always" in MUT and r.corpus_tokens > 10_000_000:
        return []
    recs.append(Rec("baseline: hybrid retrieval + rerank", tuple(base_reasons), tuple(base_warn)))

    # Everything below is an escalation that must be justified by evidence, and evidence needs an evaluation set.
    if not r.has_eval_set and "no-eval-gate" not in MUT:
        recs[0] = Rec(recs[0].pattern, recs[0].reasons,
                      ("no evaluation set: build the golden set first; no escalation below is justified yet",))
        return recs

    fits = r.corpus_tokens <= LC_FILL_LIMIT * r.context_window
    if "fit-check" in MUT:
        fits = True
    # 2. Long-context stuffing / routing
    if fits and r.update_rate == "static" and not r.permission_sensitive and r.queries_per_day <= LC_MAX_QPD:
        recs.append(Rec("long-context prompt (no retrieval)",
                        (f"corpus ({r.corpus_tokens:,} tokens) fits within {LC_FILL_LIMIT:.0%} of the window and is static",),
                        ("cost per query scales with corpus size; prompt caching may change the economics (Ch. 20)",)))
    elif fits and not r.permission_sensitive and r.queries_per_day <= LC_MAX_QPD:
        recs.append(Rec("route: retrieve first, long-context fallback",
                        ("corpus fits in the window and quality-critical queries can fall back to the full prompt (S211)",),
                        ("needs a routing signal you have validated; the routing paper's quality results are for its models and data",)))

    # 3. Query-type driven patterns
    if MULTI_HOP in r.query_types:
        if r.latency_budget_ms >= ITERATIVE_LATENCY_MS or "latency-ignored" in MUT:
            recs.append(Rec("iterative retrieval / query decomposition",
                            ("questions need evidence from several documents chained together (Ch. 14)",),
                            ("each extra hop adds a model and retrieval round trip; cap hops and measure",)))
        else:
            recs.append(Rec("single-step graph-assisted retrieval (entity graph + PageRank style)",
                            ("multi-hop questions under a tight latency budget cannot afford iteration (S210)",),
                            ("graph construction needs an LLM pass over the corpus; reported speed/cost gains are the authors' (S210)",)))
    if GLOBAL in r.query_types:
        warn = ["summaries are built offline with model calls over the whole corpus: budget the indexing cost"]
        reasons = ["questions about themes across the whole corpus are not answerable from a few top-k chunks (S207)"]
        if r.update_rate == "fast" and "update-ignored" not in MUT:
            warn.append("fast-changing corpus: summary trees/communities go stale; plan incremental rebuild or scheduled rebuild with an age label")
        if r.permission_sensitive and "acl-ignored" not in MUT:
            warn.append("PERMISSION-SENSITIVE: a summary mixes content from many documents and one ACL cannot describe it; build summaries only within a single permission scope or do not use this pattern [E]")
        recs.append(Rec("hierarchical / community summaries (RAPTOR- or GraphRAG-style)", tuple(reasons), tuple(warn)))
    if STRUCTURED in r.query_types:
        recs.append(Rec("guarded text-to-SQL / semantic layer",
                        ("questions are aggregations over structured records, not passages (Ch. 29)",),
                        ("execute as a restricted role; verify the numbers path separately from prose (Ch. 29)",)))
    return recs


# ------------------------------------------------------------------ cost model (abstract units)

def lc_cost(corpus_tokens: int, question_tokens: int = 50, p_in: float = 1.0) -> float:
    return (corpus_tokens + question_tokens) * p_in


def rag_cost(k: int = 8, chunk_tokens: int = 400, question_tokens: int = 50, p_in: float = 1.0, retrieval_overhead: float = 0.0) -> float:
    return (k * chunk_tokens + question_tokens) * p_in + retrieval_overhead


def route_cost(f_rag: float, rag: float, lc: float) -> float:
    """Retrieve first; the fraction (1 - f) that the cheap path cannot answer ALSO pays the full prompt."""
    if "route-free-fallback" in MUT:
        return rag * f_rag + lc * (1 - f_rag)
    return rag + (1 - f_rag) * lc


def breakeven_fraction(rag: float, lc: float) -> float:
    """Smallest fraction answered by retrieval for routing to be no more expensive than always using the long prompt."""
    return rag / lc


# ------------------------------------------------------------------ checks

def names(rs: list[Rec]) -> list[str]:
    return [x.pattern for x in rs]


def has(rs: list[Rec], needle: str) -> bool:
    return any(needle in x.pattern for x in rs)


def warns(rs: list[Rec], needle: str) -> bool:
    return any(needle in w for x in rs for w in x.warnings)


def R(**kw: object) -> Requirements:
    base = dict(corpus_tokens=2_000_000, context_window=200_000)
    base.update(kw)
    return Requirements(**base)  # type: ignore[arg-type]


def check_scenarios() -> None:
    # S1 large corpus, plain lookups: baseline only
    s = select_patterns(R(corpus_tokens=50_000_000))
    assert names(s) == ["baseline: hybrid retrieval + rerank"], names(s)
    # S2 small static corpus: long-context becomes an option
    s = select_patterns(R(corpus_tokens=60_000, update_rate="static"))
    assert has(s, "long-context prompt"), names(s)
    # S3 small, changing corpus: route rather than stuff
    s = select_patterns(R(corpus_tokens=60_000, update_rate="fast"))
    assert has(s, "route:") and not has(s, "long-context prompt"), names(s)
    # S4 exactly at the 50% fill limit still fits; one token over does not
    s = select_patterns(R(corpus_tokens=100_000, update_rate="static"))
    assert has(s, "long-context prompt"), names(s)
    s = select_patterns(R(corpus_tokens=100_001, update_rate="static"))
    assert not has(s, "long-context") and not has(s, "route:"), names(s)
    # S5 permission-sensitive small static corpus: never stuffed into a shared prompt
    s = select_patterns(R(corpus_tokens=60_000, update_rate="static", permission_sensitive=True))
    assert not has(s, "long-context") and not has(s, "route:"), names(s)
    assert any("ACL" in x for x in s[0].reasons)
    # S6 very high traffic disqualifies stuffing even for a small static corpus
    s = select_patterns(R(corpus_tokens=60_000, update_rate="static", queries_per_day=LC_MAX_QPD + 1))
    assert not has(s, "long-context"), names(s)
    s = select_patterns(R(corpus_tokens=60_000, update_rate="static", queries_per_day=LC_MAX_QPD))
    assert has(s, "long-context"), "the threshold itself is allowed"
    # S7 multi-hop with a relaxed budget: iterate; with a tight one: single-step graph
    s = select_patterns(R(query_types=frozenset({LOOKUP, MULTI_HOP}), latency_budget_ms=ITERATIVE_LATENCY_MS))
    assert has(s, "iterative") and not has(s, "single-step graph"), names(s)
    s = select_patterns(R(query_types=frozenset({LOOKUP, MULTI_HOP}), latency_budget_ms=ITERATIVE_LATENCY_MS - 1))
    assert has(s, "single-step graph") and not has(s, "iterative"), names(s)
    # S8 global questions: summaries, with a stale warning when the corpus changes fast
    s = select_patterns(R(query_types=frozenset({GLOBAL})))
    assert has(s, "hierarchical") and not warns(s, "stale"), names(s)
    s = select_patterns(R(query_types=frozenset({GLOBAL}), update_rate="fast"))
    assert warns(s, "stale")
    # S9 global questions over permissioned content: warning is mandatory
    s = select_patterns(R(query_types=frozenset({GLOBAL}), permission_sensitive=True))
    assert warns(s, "PERMISSION-SENSITIVE")
    s = select_patterns(R(query_types=frozenset({GLOBAL}), permission_sensitive=False))
    assert not warns(s, "PERMISSION-SENSITIVE")
    # S10 structured questions: text-to-SQL
    s = select_patterns(R(query_types=frozenset({STRUCTURED})))
    assert has(s, "text-to-SQL")
    # S11 no evaluation set: baseline only, with the reason
    s = select_patterns(R(query_types=frozenset({LOOKUP, MULTI_HOP, GLOBAL, STRUCTURED}), has_eval_set=False))
    assert names(s) == ["baseline: hybrid retrieval + rerank"] and warns(s, "golden set")
    # S12 everything at once with an evaluation set: all three escalations present, in query-type order
    s = select_patterns(R(query_types=frozenset(QUERY_TYPES)))
    assert [has(s, k) for k in ("iterative", "hierarchical", "text-to-SQL")] == [True, True, True]


def check_invariants() -> int:
    """Properties over a grid of requirement sets (not just the hand-picked ones)."""
    n = 0
    types = [frozenset(c) for k in range(0, 5) for c in itertools.combinations(sorted(QUERY_TYPES), k)]
    for corpus, window, qt, perm, upd, lat, qpd, ev in itertools.product(
            [1_000, 60_000, 100_000, 100_001, 5_000_000], [128_000, 200_000], types, [False, True],
            ["static", "slow", "fast"], [1_000, 3_000, 8_000], [100, 6_000], [False, True]):
        r = Requirements(corpus, window, qt, perm, upd, lat, qpd, ev)
        s = select_patterns(r)
        n += 1
        assert s and s[0].pattern.startswith("baseline"), r                      # baseline first, always
        assert all(x.reasons for x in s), r                                      # no recommendation without a reason
        if not ev:
            assert len(s) == 1, r                                                # nothing advanced without evaluation
        if perm and (has(s, "long-context") or has(s, "route:")):
            raise AssertionError(("shared prompt for permissioned corpus", r))
        if GLOBAL in qt and perm and ev:
            assert warns(s, "PERMISSION-SENSITIVE"), r
        if corpus > LC_FILL_LIMIT * window:
            assert not has(s, "long-context") and not has(s, "route:"), r        # never stuff what cannot fit
        # monotone: adding a query type never removes a recommendation
        for extra in QUERY_TYPES - qt:
            s2 = select_patterns(Requirements(corpus, window, qt | {extra}, perm, upd, lat, qpd, ev))
            assert set(names(s)) <= set(names(s2)) | {x for x in names(s) if x.startswith("iterative") or x.startswith("single-step")}, (r, extra)
    return n


def check_cost_model() -> dict[str, float]:
    lc = lc_cost(2_000_000)
    rag = rag_cost()
    assert lc == 2_000_050.0 and rag == 3_250.0
    f_star = breakeven_fraction(rag, lc)
    assert abs(f_star - 3_250 / 2_000_050) < 1e-12
    # at the break-even fraction, routing costs exactly the long prompt; above it cheaper; below it dearer
    assert abs(route_cost(f_star, rag, lc) - lc) < 1e-6
    assert route_cost(f_star + 0.01, rag, lc) < lc < route_cost(f_star - 0.001, rag, lc)
    # with nothing answerable by retrieval, routing is strictly worse than always stuffing (the fallback is not free)
    assert route_cost(0.0, rag, lc) == rag + lc > lc
    # with everything answerable it costs exactly the retrieval path
    assert route_cost(1.0, rag, lc) == rag
    # the cheaper the long prompt relative to retrieval, the higher the fraction retrieval must answer
    small = lc_cost(20_000)
    assert breakeven_fraction(rag, small) > breakeven_fraction(rag, lc)
    # and when the corpus is small enough that stuffing is cheaper than retrieval, routing never wins
    tiny = lc_cost(2_000)
    assert breakeven_fraction(rag, tiny) > 1.0 and route_cost(1.0, rag, tiny) > tiny
    return {"lc": lc, "rag": rag, "break_even_fraction": f_star, "ratio_lc_over_rag": lc / rag,
            "break_even_small_corpus_20k": breakeven_fraction(rag, small), "route_at_80pct": route_cost(0.8, rag, lc)}


def run_checks() -> dict[str, object]:
    check_scenarios()
    n = check_invariants()
    c = check_cost_model()
    return {"grid_cases": n, **c}


def main() -> None:
    r = run_checks()
    print(f"12 constructed scenarios OK; invariants held on {r['grid_cases']:,} requirement sets")
    print(f"cost model (abstract units, corpus 2M tokens vs 8x400-token retrieval): long prompt {r['lc']:,.0f} | retrieval {r['rag']:,.0f} "
          f"| ratio {r['ratio_lc_over_rag']:.0f}x | break-even answered-by-retrieval fraction {r['break_even_fraction']:.4%}")
    print(f"with a 20k-token corpus the break-even fraction is {r['break_even_small_corpus_20k']:.1%}; routing at 80% retrieval-answered on the 2M corpus costs {r['route_at_80pct']:,.0f} "
          f"({r['route_at_80pct'] / r['lc']:.1%} of always stuffing)")
    print("OK: all assertions hold (rules are engineering judgement; prices are abstract; quality of the cheaper path is not modelled).")


MUTANT_NAMES = ["baseline-always", "no-eval-gate", "fit-check", "latency-ignored", "update-ignored", "acl-ignored", "route-free-fallback"]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except (AssertionError, KeyError, ZeroDivisionError):
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    if survived:
        print("SURVIVED:", survived)
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
