"""Chapter 6 exercise: an end-to-end retrieval workflow on a toy corpus (stdlib only).

Stages: two candidate generators -> Reciprocal Rank Fusion -> MMR diversity ->
context assembly under a budget -> retrieval metrics.

LIMITS - read before quoting any number
  * The corpus has 10 hand-written chunks and 4 queries. Metric values are
    illustrative of HOW to compute and read metrics, not evidence about any real
    system or method.
  * "Lexical" = a toy term-overlap scorer (NOT BM25; Chapter 9 covers lexical
    ranking properly). "Dense" = a character-trigram hashing vector with cosine
    similarity, a stand-in for an embedding model. It captures spelling
    similarity, not meaning. Do not infer anything about real embeddings.
  * What IS verified here: the mechanics (RRF arithmetic, MMR behaviour,
    metric formulas, budgeted ordered assembly).

Run:  python -I ch06_retrieval_pipeline.py
"""
from __future__ import annotations

import math
import re
import zlib
from collections import Counter

# ----------------------------------------------------------------- corpus -----
CHUNKS: dict[str, str] = {
    "c1": "ADR-017 rejected Kafka for the ingestion queue because of operational overhead.",
    "c2": "ADR-017 rejected Kafka for the ingestion queue because of the operational overhead for the team.",  # copy of c1 from another folder, lightly edited
    "c3": "Runbook: error E-4471 means the vector index is rebuilding. Wait for the rebuild to finish.",
    "c4": "Parental leave policy: employees receive 16 weeks of paid leave.",
    "c5": "Contractors are not covered by the parental leave policy unless their contract says otherwise.",
    "c6": "The ingestion queue uses Azure Service Bus with dead-letter handling.",
    "c7": "Expense policy: meals above 50 euros require a receipt.",
    "c8": "Index rebuilds are triggered when the embedding model changes.",
    "c9": "Travel policy: book flights at least 14 days in advance.",
    "c10": "Security runbook: rotate API keys every 90 days.",
}

# graded relevance judgments per query (0 = irrelevant, 1 = partial, 2 = fully answers)
QUERIES: dict[str, dict[str, int]] = {
    "why did we drop kafka": {"c1": 2, "c2": 2, "c6": 1},
    "E-4471": {"c3": 2, "c8": 1},
    "parental leave for contractors": {"c5": 2, "c4": 1},
    "queue dead letter": {"c6": 2},
}


# ---------------------------------------------------------------- scorers -----
def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9\-]+", s.lower())


def lexical_scores(q: str) -> dict[str, float]:
    qt = Counter(tokens(q))
    out = {}
    for cid, text in CHUNKS.items():
        dt = Counter(tokens(text))
        out[cid] = float(sum(min(qt[t], dt[t]) for t in qt))
    return out


def trigram_vec(s: str, dim: int = 256) -> list[float]:
    s = " " + re.sub(r"[^a-z0-9]+", " ", s.lower()) + " "
    v = [0.0] * dim
    for i in range(len(s) - 2):
        v[zlib.crc32(s[i : i + 3].encode()) % dim] += 1.0   # stable across runs (str hash() is randomized)
    return v


def cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return 0.0 if na == 0 or nb == 0 else sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def dense_scores(q: str) -> dict[str, float]:
    qv = trigram_vec(q)
    return {cid: cos(qv, trigram_vec(t)) for cid, t in CHUNKS.items()}


def ranked(scores: dict[str, float], top: int) -> list[str]:
    return [c for c, s in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if s > 0][:top]


# ---------------------------------------------------------------- fusion ------
def rrf(lists: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion: score(d) = sum over lists of 1 / (k + rank(d)), rank starting at 1."""
    score: dict[str, float] = {}
    for lst in lists:
        for rank, d in enumerate(lst, start=1):
            score[d] = score.get(d, 0.0) + 1.0 / (k + rank)
    return sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------- MMR ---------
def jaccard(a: str, b: str) -> float:
    A, B = set(tokens(a)), set(tokens(b))
    return len(A & B) / len(A | B) if A | B else 0.0


def mmr(candidates: list[str], rel: dict[str, float], lam: float, n: int) -> list[str]:
    """Greedy MMR: argmax lam*rel(d) - (1-lam)*max_sim(d, selected). Relevance is min-max scaled to [0,1]."""
    lo, hi = min(rel[c] for c in candidates), max(rel[c] for c in candidates)
    norm = {c: (rel[c] - lo) / (hi - lo) if hi > lo else 1.0 for c in candidates}
    chosen: list[str] = []
    pool = list(candidates)
    while pool and len(chosen) < n:
        def val(c: str) -> float:
            red = max((jaccard(CHUNKS[c], CHUNKS[s]) for s in chosen), default=0.0)
            return lam * norm[c] - (1 - lam) * red
        best = max(pool, key=lambda c: (val(c), -int(c[1:])))
        chosen.append(best)
        pool.remove(best)
    return chosen


def dedupe(order: list[str], threshold: float) -> list[str]:
    """Keep the first of any pair whose token Jaccard similarity exceeds the threshold."""
    kept: list[str] = []
    for c in order:
        if all(jaccard(CHUNKS[c], CHUNKS[k]) <= threshold for k in kept):
            kept.append(c)
    return kept


# ---------------------------------------------------------------- metrics -----
def precision_at_k(ranked_ids: list[str], rel: dict[str, int], k: int) -> float:
    return sum(1 for d in ranked_ids[:k] if rel.get(d, 0) > 0) / k


def recall_at_k(ranked_ids: list[str], rel: dict[str, int], k: int) -> float:
    total = sum(1 for v in rel.values() if v > 0)
    return sum(1 for d in ranked_ids[:k] if rel.get(d, 0) > 0) / total if total else 0.0


def reciprocal_rank(ranked_ids: list[str], rel: dict[str, int]) -> float:
    for i, d in enumerate(ranked_ids, start=1):
        if rel.get(d, 0) > 0:
            return 1.0 / i
    return 0.0


def dcg(gains: list[float]) -> float:
    """Linear-gain DCG: sum rel_i / log2(i + 1)."""
    return sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))


def ndcg_at_k(ranked_ids: list[str], rel: dict[str, int], k: int) -> float:
    gains = [float(rel.get(d, 0)) for d in ranked_ids[:k]]
    ideal = sorted((float(v) for v in rel.values()), reverse=True)[:k]
    return dcg(gains) / dcg(ideal) if dcg(ideal) > 0 else 0.0


# ---------------------------------------------------------------- assembly ----
def assemble(order: list[str], budget_words: int) -> list[str]:
    """Take chunks in the given order until the word budget is exhausted (never truncate mid-chunk)."""
    out, used = [], 0
    for c in order:
        w = len(CHUNKS[c].split())
        if used + w > budget_words:
            continue
        out.append(c)
        used += w
    return out


def edge_order(best_first: list[str]) -> list[str]:
    """Place the strongest chunks at the START and END, weakest in the middle."""
    front, back = [], []
    for i, c in enumerate(best_first):
        (front if i % 2 == 0 else back).append(c)
    return front + back[::-1]


# ---------------------------------------------------------------- main --------
def main() -> None:
    # --- RRF arithmetic, verified by hand ---------------------------------------------------
    fused = dict(rrf([["a", "b", "c"], ["c", "a", "d"]], k=60))
    assert math.isclose(fused["a"], 1 / 61 + 1 / 62)          # rank 1 in list 1, rank 2 in list 2
    assert math.isclose(fused["c"], 1 / 63 + 1 / 61)          # rank 3 and rank 1
    assert fused["a"] > fused["c"] > fused["b"]               # agreement beats a single high rank
    # an item ranked 1st in one list and absent from another loses to one ranked 2nd in both
    f2 = dict(rrf([["x", "y"], ["z", "y"]], k=60))
    assert f2["y"] > f2["x"] and f2["y"] > f2["z"]
    print("RRF arithmetic and agreement property: OK")

    # --- metric formulas on a hand-computed case ---------------------------------------------
    rel = {"d1": 1, "d3": 1}                                     # binary relevance
    r = ["d1", "d2", "d3"]
    assert math.isclose(precision_at_k(r, rel, 3), 2 / 3)
    assert math.isclose(recall_at_k(r, rel, 3), 1.0)
    assert math.isclose(reciprocal_rank(["d2", "d1"], rel), 0.5)
    # DCG = 1/log2(2) + 0 + 1/log2(4) = 1.5 ; IDCG = 1 + 1/log2(3) = 1.6309 ; nDCG = 0.9197
    assert math.isclose(ndcg_at_k(r, rel, 3), 1.5 / (1 + 1 / math.log2(3)))
    assert round(ndcg_at_k(r, rel, 3), 4) == 0.9197
    assert math.isclose(ndcg_at_k(["d1", "d3", "d2"], rel, 3), 1.0)      # ideal order -> 1.0
    print("Metric formulas verified against hand computation (nDCG@3 = 0.9197 for [rel,non,rel]): OK")

    # --- MMR removes the near-duplicate -----------------------------------------------------
    q = "why did we drop kafka"
    lex, den = lexical_scores(q), dense_scores(q)
    cand_l, cand_d = ranked(lex, 6), ranked(den, 6)
    fused_list = rrf([cand_l, cand_d])
    top = [c for c, _ in fused_list][:6]
    rel_scores = dict(fused_list)
    assert jaccard(CHUNKS["c1"], CHUNKS["c2"]) > 0.8, "c1/c2 are near-duplicates by construction"
    div = mmr(top, rel_scores, lam=0.5, n=3)
    plain = top[:3]
    print(f"\nquery: {q!r}")
    print(f"  lexical top : {cand_l[:4]}")
    print(f"  dense top   : {cand_d[:4]}")
    print(f"  RRF fused   : {top[:4]}")
    print(f"  plain top-3 : {plain}")
    print(f"  MMR top-3   : {div}")
    # Finding 1: MMR DEMOTES the duplicate (rank 2 -> 3) but does not remove it.
    assert plain.index("c2") == 1 and div.index("c2") > plain.index("c2")
    # Finding 2: the cost of diversity - an irrelevant chunk (judged 0) now outranks the relevant duplicate.
    rel_k = QUERIES[q]
    assert rel_k.get("c7", 0) == 0 and div.index("c7") < div.index("c2")
    # lambda = 1.0 must reproduce the plain relevance order.
    assert mmr(top, rel_scores, lam=1.0, n=3) == plain
    # Finding 3: for TRUE duplicates, explicit near-duplicate removal is the right tool.
    deduped = dedupe(top, threshold=0.8)
    assert "c1" in deduped and "c2" not in deduped
    assert deduped[:2] == ["c1", "c7"]   # the freed slot goes to the next candidate, relevant or not
    print(f"  dedupe(J>0.8): {deduped[:3]}")

    # --- assembly: budget respected, edge ordering places best at both ends --------------------
    best_first = [c for c, _ in fused_list][:5]
    order = edge_order(best_first)
    assert order[0] == best_first[0] and order[-1] == best_first[1]
    ctx = assemble(order, budget_words=40)
    assert sum(len(CHUNKS[c].split()) for c in ctx) <= 40
    print(f"  edge order  : {order}   assembled under 40-word budget: {ctx}")

    # --- metrics per query and method (illustrative only) ------------------------------------
    print("\nper-query metrics @3 (toy data; illustrates computation, not method quality)")
    print(f"{'query':<34}{'method':<9}{'P@3':>6}{'R@3':>6}{'RR':>6}{'nDCG@3':>8}")
    for qtext, relj in QUERIES.items():
        lex, den = lexical_scores(qtext), dense_scores(qtext)
        l, d = ranked(lex, 10), ranked(den, 10)
        f = [c for c, _ in rrf([l, d])]
        for name, lst in (("lexical", l), ("dense*", d), ("fused", f)):
            print(f"{qtext:<34}{name:<9}{precision_at_k(lst, relj, 3):>6.2f}{recall_at_k(lst, relj, 3):>6.2f}"
                  f"{reciprocal_rank(lst, relj):>6.2f}{ndcg_at_k(lst, relj, 3):>8.2f}")
    print("* 'dense' = character-trigram stand-in, not a real embedding model")
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
