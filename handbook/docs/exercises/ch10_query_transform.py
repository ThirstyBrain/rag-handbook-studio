"""Chapter 10 exercise: query transformation mechanics on a toy corpus (stdlib only).

LIMITS - read before quoting anything
  * There is NO language model here. Every "LLM step" is a stand-in: a rule, a hand-written
    expansion list, or a heuristic classifier. The point is the MECHANICS and the failure modes
    (context contamination, expansion drift, routing arithmetic), not the quality of any LLM.
  * Corpus, queries and expansion lists are small and were written to make each mechanism
    visible. Results are CONSTRUCTED illustrations. Evidence about real systems comes from the
    cited papers (Weller et al.: expansion gains correlate negatively with retriever strength).
  * Latency numbers are symbolic: assumed unit costs, used only to show arithmetic.

Run:  python -I ch10_query_transform.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _toy_ir import BM25, ndcg_at_k, recall_at_k, tokens, weighted  # noqa: E402

CORPUS = {
    "d1": "Parental leave policy: employees receive sixteen weeks of paid leave after the birth or adoption of a child.",
    "d2": "Contractors are not covered by the parental leave policy unless their contract says otherwise.",
    "d3": "Laptop battery policy: replace batteries after 500 charge cycles and keep the corporate charger.",
    "d4": "Troubleshooting guide for notebook power usage: close background applications to cut energy use and extend runtime.",
    "d5": "Runbook: error E-4471 means the vector index is rebuilding. Wait for the rebuild to finish.",
    "d6": "Runbook: error E-4472 means the embedding queue is full. Scale the workers.",
    "d7": "General troubleshooting guide: if a problem or failure occurs, restart the service and contact support for the issue.",
    "d8": "Incident handling: every failure or problem must be logged as an issue with a severity and a log entry.",
    "d9": "ADR-017 rejected Kafka for the ingestion queue because of operational overhead.",
    "d10": "The ingestion queue uses Azure Service Bus with dead-letter handling.",
    "d11": "Expense policy: meals above 50 euros require a receipt.",
    "d12": "Travel policy: book flights at least 14 days in advance.",
    "d13": "Security runbook: rotate API keys every 90 days.",
    "d14": "Remote work policy: employees may work remotely up to three days per week.",
}
bm = BM25(CORPUS)


def top(query, k=3):
    return [d for d, _ in bm.search(query, k)]


# ======================================================== A. conversational rewriting ==
WH_AUX = {"what", "how", "who", "when", "where", "which", "why", "is", "are", "do", "does", "can", "about",
          "and", "long", "many", "much", "it", "that", "they", "this"}
PRONOUNS = {"it", "that", "they", "this", "those", "them", "its"}


def rule_rewrite(history: list[str], follow_up: str) -> str:
    """STAND-IN for an LLM rewriter: if the follow-up has no content words of its own, or uses a pronoun,
    borrow the content words of the previous user turn. A topic switch (own content words, no pronoun) is left alone."""
    own = [t for t in tokens(follow_up) if t not in WH_AUX]
    has_pronoun = any(t in PRONOUNS for t in follow_up.lower().replace("?", "").split())
    if own and not has_pronoun:
        return follow_up
    prev = [t for t in tokens(history[-1]) if t not in WH_AUX]
    return f"{follow_up} {' '.join(prev)}"


def naive_always_append(history: list[str], follow_up: str) -> str:
    return f"{follow_up} {' '.join(t for t in tokens(history[-1]) if t not in WH_AUX)}"


def part_a() -> None:
    print("== A. Conversational rewriting (rule-based stand-in for an LLM) ==")
    hist = ["How many weeks of parental leave do employees get?"]
    follow = "And how long is it?"
    raw_top = top(follow)
    rewritten = rule_rewrite(hist, follow)
    rew_top = top(rewritten)
    print(f"  follow-up {follow!r}: retrieves {raw_top}")
    print(f"  rewritten {rewritten!r}: retrieves {rew_top}")
    assert "d1" not in raw_top[:1], "without context the pronoun follow-up should not find the policy"
    assert rew_top[0] == "d1"

    # topic switch: a good rewriter must NOT inherit the previous topic
    switch = "What is the travel policy?"
    assert rule_rewrite(hist, switch) == switch
    contaminated = naive_always_append(hist, switch)
    print(f"  topic switch {switch!r}: selective rewrite keeps it; ALWAYS-append gives {contaminated!r} -> {top(contaminated)}")
    assert top(switch)[0] == "d12"
    assert top(contaminated)[0] != "d12", "always-append contaminates a topic switch with the previous topic"


# ===================================================== B. expansion helps and hurts ====
Q_HELP = ("laptop battery drain", {"d4": 2, "d3": 1})
Q_HURT = ("ingestion queue error", {"d10": 2, "d9": 1, "d6": 1})
EXP_HELP = ["notebook", "power", "energy", "usage"]                   # vocabulary bridge (stand-in for an LLM)
EXP_HURT = ["failure", "problem", "issue", "log", "retry"]            # generic terms an LLM might add


def part_b() -> None:
    print("\n== B. Expansion: helps on a vocabulary gap, drifts when expansion terms are generic ==")
    rows = []
    for name, (q, rel), exp in (("vocab gap", Q_HELP, EXP_HELP), ("generic expansion", Q_HURT, EXP_HURT)):
        base = [d for d, _ in bm.search(q, 10)]
        full = [d for d, _ in bm.search(weighted(q, exp, 1.0), 10)]
        damp = [d for d, _ in bm.search(weighted(q, exp, 0.3), 10)]
        rows.append((name, q, ndcg_at_k(base, rel), ndcg_at_k(full, rel), ndcg_at_k(damp, rel), base[:3], full[:3], damp[:3]))
        print(f"  {name:<18} nDCG@3: none={rows[-1][2]:.2f}  expand(w=1.0)={rows[-1][3]:.2f}  expand(w=0.3)={rows[-1][4]:.2f}"
              f"   top3 none={base[:3]} w1.0={full[:3]} w0.3={damp[:3]}")
    help_row, hurt_row = rows
    assert help_row[3] > help_row[2], "expansion should help the vocabulary-gap query"
    assert hurt_row[3] < hurt_row[2], "generic expansion at full weight should hurt this constructed query"
    assert hurt_row[4] >= hurt_row[2] - 1e-9, "down-weighting expansion terms should recover the loss here"
    # original terms are never lowered
    wt = weighted("ingestion queue error", EXP_HURT + ["queue"], 0.3)
    assert wt["queue"] == 1.0 and wt["failure"] == 0.3


# =============================================== C. decomposition, routing, latency ===
def classify(q: str) -> str:
    """STAND-IN for a trained complexity classifier (Adaptive-RAG trains a small LM)."""
    ql = q.lower()
    if " of the company that " in ql or " that created " in ql or "who founded the" in ql:
        return "multi_dependent"
    if ql.startswith("compare ") or " and also " in ql or (ql.count("?") >= 2) or " versus " in ql:
        return "multi_independent"
    return "simple"


def latency(kind: str, n_sub: int, l_llm: float, r: float) -> float:
    """Symbolic latency model with ASSUMED unit costs (seconds): l_llm = one LLM transform call, r = one retrieval."""
    if kind == "simple":
        return r
    if kind == "multi_independent":          # decompose once, retrieve sub-queries in parallel
        return l_llm + r
    if kind == "multi_dependent":            # each hop needs the previous answer: sequential
        return l_llm + n_sub * (r + l_llm)
    raise ValueError(kind)


def part_c() -> None:
    print("\n== C. Routing and latency arithmetic (assumed unit costs: LLM call 1.0, retrieval 0.2) ==")
    cases = [
        ("What is the parental leave policy?", "simple"),
        ("Who is the CEO of the company that created Zephyr?", "multi_dependent"),
        ("Compare the parental leave policy and the remote work policy", "multi_independent"),
        ("E-4471", "simple"),
        ("What does ADR-017 say about Kafka?", "simple"),
    ]
    for q, expected in cases:
        got = classify(q)
        print(f"  {got:<18} {q}")
        assert got == expected, (q, got, expected)
    L, R = 1.0, 0.2
    simple, ind, dep = latency("simple", 1, L, R), latency("multi_independent", 3, L, R), latency("multi_dependent", 3, L, R)
    print(f"  simple = {simple:.1f}s, independent x3 (parallel) = {ind:.1f}s, dependent 3 hops (sequential) = {dep:.1f}s")
    assert simple < ind < dep
    assert abs(ind - (L + R)) < 1e-12 and abs(dep - (L + 3 * (R + L))) < 1e-12
    # a transform that is applied to EVERY query adds its LLM latency to every query
    assert latency("multi_independent", 1, L, R) - latency("simple", 1, L, R) == L


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    print("\nAll assertions passed.")
