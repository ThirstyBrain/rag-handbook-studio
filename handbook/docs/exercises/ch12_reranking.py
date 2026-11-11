"""Chapter 12 exercise: re-ranking mechanics on a tiny constructed corpus (stdlib only).

IMPORTANT (OI-040, OI-043): there is NO neural model here. `pair_score` is a hand-written
stand-in for a cross-encoder: like one, it scores the (query, document) PAIR jointly instead of
embedding the two separately, so it can disagree with first-stage BM25. It has no semantic
understanding and no measured quality. What this script verifies is pipeline MECHANICS:
  A. candidate-depth ceiling (a reranker can only reorder what retrieval handed it)
  B. cost model arithmetic (theoretical, parameters are assumptions)
  C. score scale: logit vs sigmoid, why absolute thresholds are not portable
  D. input-length truncation and chunk-max aggregation
  E. context ordering (best passages at the edges) and its properties
  F. pipeline order: authorization BEFORE any text reaches the reranker; abstention on weak evidence
Run: python -I docs/exercises/ch12_reranking.py   (exit code 0 = all assertions hold)
`--mutants` additionally runs injected-defect variants and requires every one to be detected.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _toy_ir import BM25, tokens  # noqa: E402

DOCS = {
    "d01": "Hotel night rates guide: hotel rates per night vary by season. Travel desks list hotel night rates for each city. Rates per night are updated yearly.",
    "d02": "Domestic travel policy: hotel stays are reimbursed up to 150 USD per night when travelling inside the country.",
    "d03": "International travel policy: hotel stays abroad are reimbursed up to 220 USD per night. Receipts are required for every international trip.",
    "d04": "Travel booking portal: book flights and hotel rooms through the portal. Hotel booking per night is shown at checkout for international and domestic travel.",
    "d05": "Per diem for meals during international travel is 65 USD per day. Hotel costs are claimed separately.",
    "d06": "Expense report rules: submit within 30 days. Hotel, travel and meal receipts must be attached to each expense report.",
    "d07": "Corporate card: the corporate card may be used for hotel and travel expenses. International transaction fees are reimbursed.",
    "d08": "Maximum reimbursable amount for office supplies is 500 USD per quarter. Requests above the maximum need approval.",
    "d09": "Hotel loyalty programs: points earned on business travel belong to the employee. Hotel upgrades are not reimbursable.",
    "d10": "Travel insurance covers international trips. Hotel cancellations per night booked are covered when a trip is cancelled.",
    "d11": "Mileage rates for personal car travel are set per kilometre. Hotel is not included in mileage claims.",
    "d12": "Visa fees for international travel are reimbursed in full. Hotel and flight costs follow the standard travel policy.",
}
QUERY = "maximum reimbursable hotel rate per night for international travel"
RELEVANT = "d03"
BM = BM25(DOCS)


def bigrams(toks: list[str]) -> set[tuple[str, str]]:
    return set(zip(toks, toks[1:], strict=False))


def pair_score(query: str, doc: str, max_tokens: int | None = None) -> float:
    """STAND-IN for a cross-encoder: IDF-weighted query-term coverage + adjacent-pair (bigram) bonus.

    Sees query and document together; optionally truncates the document to `max_tokens` tokens
    (real rerankers have an input limit: the truncation behaviour is the point of Part D).
    """
    q, d = tokens(query), tokens(doc)
    if max_tokens is not None:
        d = d[:max_tokens]
    dset = set(d)
    cover = sum(BM.idf(t) for t in set(q) if t in dset) / sum(BM.idf(t) for t in set(q))
    pairs = bigrams(q) & bigrams(d)
    return cover + 0.25 * len(pairs)


# --------------------------------------------------------------------------- pipeline under test
def retrieve_then_rerank(query: str, depth: int, k: int, *, allowed: set[str] | None = None,
                         authz_first: bool = True, seen: list[str] | None = None) -> list[str]:
    """First stage BM25 -> (authorization) -> take `depth` candidates -> rerank -> top k.

    `seen` records every document text ID shown to the reranker (stands in for an external API call).
    """
    ranked = [d for d, _ in BM.search(query, 50)]
    if allowed is not None and authz_first:
        ranked = [d for d in ranked if d in allowed]           # filter BEFORE the candidate cut and the rerank call
    cand = ranked[:depth]
    if seen is not None:
        seen.extend(cand)
    reranked = sorted(cand, key=lambda d: (-pair_score(query, DOCS[d]), d))
    if allowed is not None and not authz_first:
        reranked = [d for d in reranked if d in allowed]       # (defective ordering, used only by mutants)
    return reranked[:k]


def edge_order(ranked: list[str]) -> list[str]:
    """Place the best items at the edges of the context and the weakest in the middle.

    ranked[0] first, ranked[1] last, ranked[2] second, ranked[3] second-to-last, ...
    """
    front: list[str] = []
    back: list[str] = []
    for i, d in enumerate(ranked):
        (front if i % 2 == 0 else back).append(d)
    return front + back[::-1]


def assert_edge_order_properties(fn) -> None:
    items = [f"r{i}" for i in range(1, 8)]                       # r1 is best
    out = fn(items)
    assert sorted(out) == sorted(items), "must be a permutation (nothing dropped or duplicated)"
    assert out[0] == "r1", "best passage must be first"
    assert out[-1] == "r2", "second-best passage must be last"
    assert out[len(out) // 2] in {"r6", "r7"}, "the weakest passages must sit in the middle"
    assert fn(["a"]) == ["a"] and fn([]) == [], "degenerate sizes"


def run_assertions(pipeline=retrieve_then_rerank, order=edge_order) -> None:
    bm_rank = [d for d, _ in BM.search(QUERY, 50)]
    # ---- A. candidate-depth ceiling
    pos = bm_rank.index(RELEVANT) + 1
    assert pos == 4, f"constructed so the relevant doc is BM25 rank 4, got {pos}"
    for depth, expect_in_top3 in [(3, False), (4, True), (8, True), (12, True)]:
        top3 = pipeline(QUERY, depth, 3)
        assert (RELEVANT in top3) == expect_in_top3, (depth, top3)
    assert RELEVANT not in pipeline(QUERY, 3, 3), "reranking cannot recover a doc outside the candidate set"
    # the stand-in is lexical, so it is fooled by the keyword-stuffed guide d01 exactly as BM25 is: depth is necessary, not sufficient
    assert pipeline(QUERY, 12, 1)[0] == "d01", "disclosed limitation: the stand-in still ranks the stuffed document first"
    # ---- E. ordering
    assert_edge_order_properties(order)
    # ---- F. authorization before the reranker
    allowed = {d for d in DOCS if d != "d03"}                    # the user may NOT read the relevant doc
    seen: list[str] = []
    out = pipeline(QUERY, 12, 3, allowed=allowed, seen=seen)
    assert "d03" not in seen, "reranker (external call) must never receive a document the user cannot read"
    assert "d03" not in out
    seen2: list[str] = []
    pipeline(QUERY, 4, 3, allowed=allowed, seen=seen2)
    assert len(seen2) == 4 and all(d in allowed for d in seen2), "candidate depth is measured AFTER authorization"


def main() -> None:
    print("== BM25 first-stage ranking and stand-in pair scores ==")
    for i, (d, s) in enumerate(BM.search(QUERY, 12), 1):
        print(f"  bm25 rank {i:2d} {d} bm25={s:5.2f} pair={pair_score(QUERY, DOCS[d]):.3f}")
    pair_rank = sorted(DOCS, key=lambda d: (-pair_score(QUERY, DOCS[d]), d))
    print("  stand-in order over ALL docs:", pair_rank[:5])

    print("\n== A. candidate depth vs where the relevant doc (d03, BM25 rank 4) ends up ==")
    for depth in (3, 4, 8, 12):
        out = retrieve_then_rerank(QUERY, depth, 3)
        print(f"  depth={depth:2d} -> top3={out}  relevant at rank {out.index(RELEVANT)+1 if RELEVANT in out else 'ABSENT'}")

    print("\n== B. cost model (THEORETICAL; per-pair time and prices below are assumed, not measured) ==")
    n, c_pair_ms, parallel = 50, 4.0, 1
    serial_ms = n * c_pair_ms / parallel
    print(f"  N={n} pairs x {c_pair_ms} ms/pair / {parallel} lane = {serial_ms:.0f} ms; N=100 -> {100*c_pair_ms/parallel:.0f} ms; N=100 with 4 lanes -> {100*c_pair_ms/4:.0f} ms")
    assert serial_ms == 200.0 and 100 * c_pair_ms / 4 == 100.0
    assert n * 2 == 100, "doubling the candidate depth doubles the pairs scored (linear in N)"

    print("\n== C. score scale ==")
    logit = -5.65234375                                           # the example raw score printed on the bge-reranker-v2-m3 model card
    sig = 1 / (1 + math.exp(-logit))
    print(f"  sigmoid({logit}) = {sig:.7f}")
    assert abs(sig - 0.003497) < 5e-7, "matches the normalised value shown on the model card (0.003497...)"
    raw = [3.1, 0.2, -1.5, -4.0]
    mapped = [1 / (1 + math.exp(-x)) for x in raw]
    assert sorted(range(4), key=lambda i: -raw[i]) == sorted(range(4), key=lambda i: -mapped[i]), "sigmoid preserves order"
    thr = 0.5
    assert [x > 0 for x in raw] == [m > thr for m in mapped], "threshold 0.5 on sigmoid == threshold 0 on logits"
    assert [x > 0.5 for x in raw] != [m > 0.5 for m in mapped], "the SAME numeric threshold means different things on different scales"
    print("  order is invariant to the monotone map; a numeric threshold is not portable across scales")

    print("\n== D. input-length limit and chunk-max aggregation ==")
    filler = " ".join(["Background"] * 60)                       # 60 tokens of irrelevant preamble
    long_doc = f"{filler} International travel policy: hotel stays abroad are reimbursed up to 220 USD per night."
    full = pair_score(QUERY, long_doc)
    clipped = pair_score(QUERY, long_doc, max_tokens=40)
    windows = [long_doc.split()[i:i + 40] for i in range(0, len(long_doc.split()), 20)]
    chunk_max = max(pair_score(QUERY, " ".join(w), max_tokens=40) for w in windows)
    print(f"  untruncated={full:.3f}  first-40-tokens only={clipped:.3f}  max over 40-token windows (stride 20)={chunk_max:.3f}")
    assert clipped < 0.05 and chunk_max > 0.5, "an answer past the input limit is invisible unless the document is windowed"
    assert chunk_max >= clipped

    print("\n== E. context ordering ==")
    ordered = edge_order(["r1", "r2", "r3", "r4", "r5"])
    print("  ranked r1..r5 ->", ordered)
    assert ordered == ["r1", "r3", "r5", "r4", "r2"]

    print("\n== F. authorization and abstention ==")
    run_assertions()
    allowed = {d for d in DOCS if d != "d03"}
    seen: list[str] = []
    out = retrieve_then_rerank(QUERY, 12, 3, allowed=allowed, seen=seen)
    print(f"  user cannot read d03 -> reranker saw {len(seen)} docs (d03 among them: {'d03' in seen}); top3={out}")
    weakest_top = max(pair_score(QUERY, DOCS[d]) for d in out)
    best_all = max(pair_score(QUERY, DOCS[d]) for d in DOCS)
    print(f"  best stand-in score among permitted docs={weakest_top:.3f} vs best overall={best_all:.3f}")
    true_answer_score = pair_score(QUERY, DOCS[RELEVANT])
    # Observed (not what I first expected): the stuffed document outscores the true answer, so ANY threshold low enough
    # to admit the true answer (<= its score) also admits the stuffed one -> abstention would NOT fire when the answer is withheld.
    assert weakest_top > true_answer_score, "a score threshold cannot reliably signal 'answer absent' with this scorer"
    assert best_all == weakest_top
    print("\nOK: all assertions hold (mechanics on a constructed corpus; no neural model involved).")


def _mutant_checks() -> None:
    def no_authz_first(q, depth, k, *, allowed=None, seen=None):
        return retrieve_then_rerank(q, depth, k, allowed=allowed, authz_first=False, seen=seen)

    def ignores_depth(q, depth, k, *, allowed=None, seen=None, authz_first=True):
        return retrieve_then_rerank(q, 12, k, allowed=allowed, seen=seen)

    mutants = {
        "authz-after-rerank": dict(pipeline=no_authz_first),
        "depth-ignored": dict(pipeline=ignores_depth),
        "edge-order-identity": dict(order=lambda r: list(r)),
        "edge-order-reversed": dict(order=lambda r: list(reversed(r))),
        "edge-order-drops-item": dict(order=lambda r: edge_order(r)[:-1] if len(r) > 1 else list(r)),
    }
    survived = []
    for name, kw in mutants.items():
        try:
            run_assertions(**kw)
            survived.append(name)
        except AssertionError:
            print(f"  mutant killed: {name}")
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(mutants)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        _mutant_checks()
