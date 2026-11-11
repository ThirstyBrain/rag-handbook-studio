"""Chapter 11 exercise: multi-query fan-out, iterative multi-hop retrieval with stopping
criteria, and graph-based retrieval (stdlib only).

LIMITS - read before quoting anything
  * No language model. "Query variants", the "reader" that extracts the next entity, and the
    entity tags are hand-written stand-ins for LLM / NER / OpenIE steps. Corpora are tiny and were
    written to make each mechanism visible: CONSTRUCTED illustrations, not evidence about real
    systems (see the cited papers for that, and note their abstract-level numbers are authors' claims).
  * Part C implements only the Personalized PageRank mechanism that HippoRAG builds on, on a toy graph.
    It is not HippoRAG and says nothing about its reported gains.

Run:  python -I ch11_multi_query_multi_hop.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _toy_ir import BM25, ndcg_at_k, recall_at_k, rrf  # noqa: E402

# ============================================================ A. multi-query + RRF ===
OFFBOARD = {
    "o1": "Offboarding checklist: revoke access and collect devices from departing staff.",
    "o2": "Account deprovisioning: disable accounts when a person leaves the company.",
    "o3": "Exit process: return laptops and badges on the last working day.",
    "o4": "Data retention policy: delete personal data after the retention period ends.",
    "o5": "Remote work policy: employees may work remotely up to three days per week.",
    "o6": "Travel policy: book flights at least 14 days in advance.",
    "o7": "Expense policy: meals above 50 euros require a receipt.",
    "o8": "Onboarding checklist: provision accounts and issue laptops to new staff and recruits.",
    "o9": "Recruitment process: interview candidates and send offers to new hires.",
    "o10": "Hiring plan: open positions for recruitment of new recruits and interns this quarter.",
}
QUERY = "what happens when someone quits"
REL = {"o1": 2, "o2": 2, "o3": 2}
VARIANTS_GOOD = ["offboarding checklist for departing staff", "disable accounts when a person leaves the company",
                 "return laptops and badges on the last working day"]
VARIANT_OFFTOPIC = "recruitment of new recruits and interns"            # a drifting variant (about hiring, not leaving)


def ranked_ids(bm: BM25, q: str, k: int = 9) -> list[str]:
    return [d for d, _ in bm.search(q, k)]


def part_a() -> None:
    print("== A. Multi-query fan-out with RRF (variants are hand-written stand-ins for an LLM) ==")
    bm = BM25(OFFBOARD)
    single = ranked_ids(bm, QUERY)
    fan = [ranked_ids(bm, QUERY)] + [ranked_ids(bm, v) for v in VARIANTS_GOOD]
    fused = [d for d, _ in rrf(fan)]
    drift = fan + [ranked_ids(bm, VARIANT_OFFTOPIC)]
    fused_drift = [d for d, _ in rrf(drift)]
    fused_weighted = [d for d, _ in rrf(drift, weights=[3.0, 1.0, 1.0, 1.0, 1.0])]
    for name, lst in (("original only", single), ("fan-out (4 lists)", fused), ("fan-out + off-topic variant", fused_drift),
                      ("same, original weighted x3", fused_weighted)):
        print(f"  {name:<30} recall@3={recall_at_k(lst, REL):.2f} nDCG@3={ndcg_at_k(lst, REL):.2f} top3={lst[:3]}")
    # (1) fan-out improves recall over the vocabulary-gap original query
    assert recall_at_k(single, REL) < recall_at_k(fused, REL), "fan-out should recover relevant documents the original query misses"
    assert ndcg_at_k(fused, REL) > ndcg_at_k(single, REL)
    # (2) CONSENSUS BIAS (observed, not planned): o8 (onboarding) is irrelevant but shares words with several GOOD variants,
    #     and RRF rewards appearing in many lists, so it reaches the top of the fused list
    assert REL.get("o8", 0) == 0 and "o8" in fused[:3]
    # (3) a drifting variant drags in documents only IT can reach (hiring documents) and displaces a relevant one
    assert not ({"o9", "o10"} & set(fused[:5])), "without the drifting variant the hiring documents stay out of the top 5"
    assert "o10" in fused_drift[:5], "the off-topic variant pulls a hiring document into the top 5"
    assert fused_drift.index("o3") > fused.index("o3"), "the drifting variant pushes the relevant o3 down a slot"
    # (4) up-weighting the ORIGINAL query does not demote the drift document here: a rank-1 hit in one list ties with
    #     every other single-list rank-1 hit, so reweighting alone is not a drift control
    assert fused_weighted.index("o10") == fused_drift.index("o10")
    assert ndcg_at_k(fused_weighted, REL) >= ndcg_at_k(fused_drift, REL)    # it does help the relevant doc o2 reach rank 1
    # the original query's only hit comes from the incidental word 'when' (a lexical accident worth disclosing)
    assert ranked_ids(bm, QUERY) == ["o2"]
    # cost: N variants = N retrievals (parallel) and 1 extra LLM call to generate them
    assert len(fan) == 4


# ============================================ B. iterative multi-hop with stopping ===
CHAIN = {
    "m1": "Zephyr is a vector database product created by Nimbus Labs.",
    "m2": "Nimbus Labs was founded in 2015 and its chief executive officer is Dana Ortiz.",
    "m3": "Dana Ortiz previously led engineering at Orion Systems.",
    "m4": "Orion Systems is headquartered in Lisbon.",
    "m5": "Zephyr winds are warm westerly winds that blow across the Mediterranean.",
    "m6": "Chief executive officer compensation survey results for 2024.",
    "m7": "Lisbon is the capital of Portugal.",
    "m8": "Vector database benchmarks compare indexing speed and recall.",
}
CYCLE = {
    "c1": "Alpha Corp is owned by Beta Corp.",
    "c2": "Beta Corp is owned by Gamma Corp.",
    "c3": "Gamma Corp is owned by Alpha Corp.",
}


def reader_next_entity(question: str, docs: list[str]) -> tuple[str | None, str | None]:
    """STAND-IN for an LLM reader: extract a bridge entity (or the final answer) from retrieved text by pattern."""
    for d in docs:
        m = re.search(r"created by ([A-Z][A-Za-z]+ [A-Z][A-Za-z]+)", d)
        if m and "CEO" in question:
            return "BRIDGE", m.group(1)
        m = re.search(r"executive officer is ([A-Z][a-z]+ [A-Z][a-z]+)", d)
        if m:
            return "ANSWER", m.group(1)
        m = re.search(r"owned by ([A-Z][a-z]+ Corp)", d)
        if m and "owned" in question:
            return "BRIDGE", m.group(1)
    return None, None


def iterate(question: str, corpus: dict[str, str], first_query: str, next_query, max_hops: int = 4, k: int = 2):
    """Iterative retrieval. Stops on: ANSWER found | no new evidence | max_hops. Records the evidence chain."""
    bm = BM25(corpus)
    seen: set[str] = set()
    chain: list[tuple[int, str, list[str]]] = []
    query, stop = first_query, "max_hops"
    for hop in range(1, max_hops + 1):
        hits = [d for d, _ in bm.search(query, k)]
        chain.append((hop, query, hits))
        new = [d for d in hits if d not in seen]
        if not new:
            stop = "no_new_evidence"
            break
        seen.update(new)
        kind, ent = reader_next_entity(question, [corpus[d] for d in hits])
        if kind == "ANSWER":
            return ent, chain, "answer_found"
        if kind is None:
            stop = "reader_found_nothing"
            break
        query = next_query(ent)
    return None, chain, stop


def part_b() -> None:
    print("\n== B. Iterative multi-hop retrieval (reader is a regex stand-in for an LLM) ==")
    question = "Who is the CEO of the company that created Zephyr?"
    bm = BM25(CHAIN)
    single = [d for d, _ in bm.search(question, 3)]
    print(f"  single pass top-3: {single}   (gold chain: m1 -> m2)")
    assert "m2" not in single, "single-pass retrieval should miss the second hop (CEO vs 'chief executive officer', no company name)"
    ans, chain, stop = iterate(question, CHAIN, question, lambda ent: f"chief executive officer {ent}")
    for hop, q, hits in chain:
        print(f"  hop {hop}: query={q!r} -> {hits}")
    print(f"  answer={ans!r} stop_reason={stop}")
    assert ans == "Dana Ortiz" and stop == "answer_found" and len(chain) == 2
    assert chain[0][2][0] == "m1" and chain[1][2][0] == "m2"

    # stopping criteria on a cyclic corpus: must terminate, never loop forever
    ans2, chain2, stop2 = iterate("who owned Alpha Corp", CYCLE, "Alpha Corp owned", lambda ent: f"{ent} owned", max_hops=10)
    print(f"  cyclic corpus: hops={len(chain2)} stop_reason={stop2} answer={ans2!r}")
    assert ans2 is None and stop2 in ("no_new_evidence", "max_hops") and len(chain2) <= 10
    assert stop2 == "no_new_evidence", "the visited-set rule should stop the cycle before max_hops"
    # the hard cap protects even if the evidence rule were absent
    _, chain3, stop3 = iterate("who owned Alpha Corp", CYCLE, "Alpha Corp owned", lambda ent: f"{ent} owned", max_hops=1)
    assert len(chain3) == 1 and stop3 == "max_hops"


# ============================================== C. graph retrieval (PPR mechanism) ===
ENTITIES = {  # hand-tagged entities per document (stand-in for NER / OpenIE)
    "m1": ["Zephyr", "Nimbus Labs"],
    "m2": ["Nimbus Labs", "Dana Ortiz"],
    "m3": ["Dana Ortiz", "Orion Systems"],
    "m4": ["Orion Systems", "Lisbon"],
    "m5": ["Zephyr winds", "Mediterranean"],
    "m6": ["CEO compensation"],
    "m7": ["Lisbon", "Portugal"],
    "m8": ["Vector database"],
}


def ppr(edges: dict[str, set[str]], seeds: dict[str, float], alpha: float = 0.85, iters: int = 100) -> dict[str, float]:
    nodes = sorted(edges)
    p0 = {n: seeds.get(n, 0.0) for n in nodes}
    z = sum(p0.values())
    p0 = {n: v / z for n, v in p0.items()}
    p = dict(p0)
    for _ in range(iters):
        nxt = {n: (1 - alpha) * p0[n] for n in nodes}
        for n in nodes:
            out = edges[n]
            if not out:
                continue
            share = alpha * p[n] / len(out)
            for m in out:
                nxt[m] += share
        p = nxt
    return p


def part_c() -> None:
    print("\n== C. Graph retrieval: Personalized PageRank mechanism on a hand-tagged toy graph ==")
    edges: dict[str, set[str]] = {}
    for ents in ENTITIES.values():
        for e in ents:
            edges.setdefault(e, set())
        for a in ents:
            for b in ents:
                if a != b:
                    edges[a].add(b)
    scores = ppr(edges, {"Zephyr": 1.0})
    ordered = sorted(scores.items(), key=lambda kv: -kv[1])
    print("  PPR from seed 'Zephyr':", [(e, round(s, 3)) for e, s in ordered[:6]])
    assert abs(sum(scores.values()) - 1.0) < 1e-6
    assert scores["Nimbus Labs"] > scores["Dana Ortiz"] > scores["Orion Systems"] > scores["Lisbon"] > scores["Portugal"]
    assert scores["Dana Ortiz"] > scores["CEO compensation"] and scores["Dana Ortiz"] > scores["Vector database"]
    doc_scores = {d: sum(scores.get(e, 0.0) for e in ents) for d, ents in ENTITIES.items()}
    top3 = [d for d, _ in sorted(doc_scores.items(), key=lambda kv: -kv[1])][:3]
    print(f"  documents ranked by entity PPR mass, top-3: {top3}   (single step, no iteration)")
    assert "m2" in top3, "the second-hop document is reachable in one graph step"
    bm = BM25(CHAIN)
    assert "m2" not in [d for d, _ in bm.search("Who is the CEO of the company that created Zephyr?", 3)]


# ========================================== D. fan-out latency, budgets, partial results ===
def run_budgeted(step_costs: list[float], budget: float) -> tuple[int, float, bool]:
    """Sequential steps until the time budget is exhausted. Returns (steps completed, time used, truncated)."""
    used, done = 0.0, 0
    for c in step_costs:
        if used + c > budget:
            return done, used, True
        used += c
        done += 1
    return done, used, False


def part_d() -> None:
    print("\n== D. Latency arithmetic and budgets (assumed unit costs) ==")
    r = [0.20, 0.35, 0.25, 0.30]                                   # four sub-query retrieval times, seconds (assumed)
    parallel, sequential = max(r), sum(r)
    print(f"  fan-out of 4 retrievals: parallel = {parallel:.2f}s, sequential = {sequential:.2f}s")
    assert parallel < sequential and parallel == 0.35 and abs(sequential - 1.10) < 1e-9
    hops = [1.2, 1.2, 1.2, 1.2]                                    # each hop = LLM call + retrieval (assumed)
    done, used, truncated = run_budgeted(hops, budget=3.0)
    print(f"  iterative hops under a 3.0s budget: completed={done} used={used:.1f}s truncated={truncated}")
    assert (done, truncated) == (2, True), "a time budget must cap iteration and flag truncation"
    assert run_budgeted(hops, budget=10.0) == (4, 4.8, False)


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    part_d()
    print("\nAll assertions passed.")
