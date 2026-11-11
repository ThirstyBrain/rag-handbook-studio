"""Chapter 9 exercise: BM25 behaviour and fusion mechanics (stdlib only).

Part A  BM25: verifies the BEHAVIOURS that Elastic's "Practical BM25" article describes
        (k1 = 0 -> only IDF matters; b = 0 -> no length effect; term-frequency
        saturation; rarer terms weigh more; defaults k1 = 1.2, b = 0.75).
        The scoring formula below is the common textbook/Lucene form; the Elastic page
        shows its formula as an image, so the formula TEXT itself is not verified
        against it. Only the described behaviours are asserted.
Part B  Fusion mechanics on synthetic score lists: why naive score addition is
        dominated by the larger scale; how min-max normalisation reacts to an outlier
        while RRF does not; how the RRF constant k trades top-rank dominance for
        consensus; how weights change a fused ranking.
Part C  A toy hybrid run (illustrative only; NOT evidence about real hybrid search).

Run:  python -I ch09_hybrid_search.py
"""
from __future__ import annotations

import math
import re
import zlib
from collections import Counter


# ================================================================= Part A: BM25 =
def tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = {d: Counter(tokens(t)) for d, t in docs.items()}
        self.len = {d: sum(c.values()) for d, c in self.tf.items()}
        self.N = len(docs)
        self.avg = sum(self.len.values()) / self.N
        self.df: Counter[str] = Counter()
        for c in self.tf.values():
            self.df.update(c.keys())

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1.0 + (self.N - n + 0.5) / (n + 0.5))

    def score(self, query: str, doc: str) -> float:
        s = 0.0
        for t in tokens(query):
            f = self.tf[doc].get(t, 0)
            if f == 0:
                continue
            norm = 1.0 - self.b + self.b * self.len[doc] / self.avg
            s += self.idf(t) * f * (self.k1 + 1.0) / (f + self.k1 * norm)
        return s

    def rank(self, query: str) -> list[tuple[str, float]]:
        sc = {d: self.score(query, d) for d in self.tf}
        return sorted(((d, s) for d, s in sc.items() if s > 0), key=lambda x: (-x[1], x[0]))


def part_a() -> None:
    print("== A. BM25 behaviours described by Elastic's article ==")
    filler = " ".join(f"w{i}" for i in range(40))
    docs = {
        "tf1": "kafka " + filler,
        "tf2": "kafka kafka " + filler,
        "tf4": "kafka kafka kafka kafka " + filler,
        "tf8": "kafka " * 8 + filler,
        "short": "kafka rebuild",
        "long": "kafka rebuild " + " ".join(f"x{i}" for i in range(60)),
        "other1": "queue broker " + filler,
        "other2": "index vector " + filler,
        "rare": "zzyzx " + filler,
    }

    default = BM25(docs)
    assert (default.k1, default.b) == (1.2, 0.75)          # Elastic documents these defaults

    # (1) k1 = 0: term frequency is irrelevant, only IDF contributes
    z = BM25(docs, k1=0.0)
    assert math.isclose(z.score("kafka", "tf1"), z.score("kafka", "tf8"))
    assert math.isclose(z.score("kafka", "tf1"), z.idf("kafka"))
    print("k1=0 -> score == IDF, independent of tf: OK")

    # (2) b = 0: no length normalisation; b = 0.75: shorter doc scores higher
    nb = BM25(docs, b=0.0)
    assert math.isclose(nb.score("kafka rebuild", "short"), nb.score("kafka rebuild", "long"))
    assert default.score("kafka rebuild", "short") > default.score("kafka rebuild", "long")
    print("b=0 -> length ignored; b=0.75 -> shorter field wins: OK")

    # (3) saturation: monotone increasing with strictly diminishing increments
    s = [default.score("kafka", d) for d in ("tf1", "tf2", "tf4", "tf8")]
    assert s == sorted(s)
    inc = [(s[1] - s[0]) / 1, (s[2] - s[1]) / 2, (s[3] - s[2]) / 4]   # per extra occurrence
    assert inc[0] > inc[1] > inc[2] > 0
    print(f"tf saturation: scores {['%.3f' % v for v in s]}, gain per extra occurrence {['%.3f' % v for v in inc]}: OK")

    # (4) IDF: rarer term weighs more
    # df: zzyzx=1 doc, kafka=6 docs, w1=7 docs (of 9)
    assert default.idf("zzyzx") > default.idf("kafka") > default.idf("w1")
    print("rarer term -> higher IDF: OK")


# ============================================================ Part B: fusion =====
def rrf(lists: list[list[str]], k: float = 60, weights: list[float] | None = None) -> list[tuple[str, float]]:
    w = weights or [1.0] * len(lists)
    sc: dict[str, float] = {}
    for wi, lst in zip(w, lists, strict=True):
        for r, d in enumerate(lst, start=1):
            sc[d] = sc.get(d, 0.0) + wi / (k + r)
    return sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))


def minmax(scores: dict[str, float]) -> dict[str, float]:
    lo, hi = min(scores.values()), max(scores.values())
    return {d: (v - lo) / (hi - lo) if hi > lo else 0.0 for d, v in scores.items()}


def linear_minmax(a: dict[str, float], b: dict[str, float], wa: float = 1.0, wb: float = 1.0) -> list[tuple[str, float]]:
    na, nb = minmax(a), minmax(b)
    docs = set(a) | set(b)
    sc = {d: wa * na.get(d, 0.0) + wb * nb.get(d, 0.0) for d in docs}   # missing in a list contributes 0
    return sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))


def order(res: list[tuple[str, float]], subset: set[str] | None = None) -> list[str]:
    return [d for d, _ in res if subset is None or d in subset]


def part_b() -> None:
    print("\n== B. Fusion mechanics on synthetic scores ==")
    # (1) scale dominance of naive addition
    bm25 = {"a": 9.0, "b": 8.5, "c": 3.0, "d": 2.0}          # unbounded scale
    cos_ = {"a": 0.30, "b": 0.35, "c": 0.90, "d": 0.88}      # bounded, narrow spread
    naive = sorted(((d, bm25[d] + cos_[d]) for d in bm25), key=lambda x: -x[1])
    assert [d for d, _ in naive] == sorted(bm25, key=lambda d: -bm25[d]), "naive sum follows the larger-scale list"
    lin = order(linear_minmax(bm25, cos_))
    assert lin != [d for d, _ in naive]
    print(f"naive sum order {[d for d, _ in naive]} == BM25 order; min-max fusion {lin}: OK")

    # (2) outlier sensitivity: min-max flips a-vs-d, RRF does not
    lex_wo = {"a": 5.0, "b": 4.5, "c": 1.0, "d": 0.5}
    den_wo = {"a": 0.2, "b": 0.9, "c": 0.85, "d": 0.8}
    lex_w = {**lex_wo, "z": 50.0}
    den_w = {**den_wo, "z": 0.1}
    sub = {"a", "b", "c", "d"}
    mm_wo = order(linear_minmax(lex_wo, den_wo), sub)
    mm_w = order(linear_minmax(lex_w, den_w), sub)
    rk = lambda s: [d for d, _ in sorted(s.items(), key=lambda kv: (-kv[1], kv[0]))]  # noqa: E731
    rrf_wo = order(rrf([rk(lex_wo), rk(den_wo)]), sub)
    rrf_w = order(rrf([rk(lex_w), rk(den_w)]), sub)
    assert mm_wo.index("a") < mm_wo.index("d") and mm_w.index("a") > mm_w.index("d"), (mm_wo, mm_w)
    assert rrf_wo.index("a") < rrf_wo.index("d") and rrf_w.index("a") < rrf_w.index("d"), (rrf_wo, rrf_w)
    assert rrf_wo[0] == rrf_w[0] == "b" and rrf_wo[-1] == rrf_w[-1] == "d"
    print(f"min-max: {mm_wo} -> {mm_w} after adding one outlier (a falls below d)")
    print(f"RRF    : {rrf_wo} -> {rrf_w} (a stays above d): OK")

    # (3) k: top-rank dominance vs consensus
    l1, l2 = ["A", "x1", "x2", "x3"], ["y1", "y2", "B", "y4"]
    l1 = ["A", "n1", "B", "n2"]            # A: rank 1 in list 1 only; B: rank 3 in both lists
    l2 = ["m1", "m2", "B", "m3"]
    r_k0 = dict(rrf([l1, l2], k=0))
    r_k60 = dict(rrf([l1, l2], k=60))
    assert r_k0["A"] > r_k0["B"], "k=0: a single rank-1 beats two rank-3s (1 vs 2/3)"
    assert r_k60["B"] > r_k60["A"], "k=60: consensus (2/63) beats a lone rank-1 (1/61)"
    print(f"k=0: A={r_k0['A']:.3f} > B={r_k0['B']:.3f};  k=60: B={r_k60['B']:.4f} > A={r_k60['A']:.4f}: OK")

    # (4) weights
    a_list, b_list = ["p", "q", "r"], ["r", "q", "p"]
    eq = order(rrf([a_list, b_list]))
    w = order(rrf([a_list, b_list], weights=[2.0, 1.0]))
    assert eq[0] != w[0] or eq != w
    assert w[0] == "p"
    print(f"equal weights {eq} vs weights [2,1] {w}: OK")


# ============================================================ Part C: toy run ====
def trigram_vec(s: str, dim: int = 256) -> list[float]:
    s = " " + re.sub(r"[^a-z0-9]+", " ", s.lower()) + " "
    v = [0.0] * dim
    for i in range(len(s) - 2):
        v[zlib.crc32(s[i : i + 3].encode()) % dim] += 1.0
    return v


def cos(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return 0.0 if not na or not nb else sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


CORPUS = {
    "d1": "ADR-017 rejected Kafka for the ingestion queue because of operational overhead.",
    "d2": "Runbook: error E-4471 means the vector index is rebuilding. Wait for the rebuild to finish.",
    "d3": "Parental leave policy: employees receive 16 weeks of paid leave.",
    "d4": "Contractors are not covered by the parental leave policy unless their contract says otherwise.",
    "d5": "The ingestion queue uses Azure Service Bus with dead-letter handling.",
    "d6": "Index rebuilds are triggered when the embedding model changes.",
    "d7": "Expense policy: meals above 50 euros require a receipt.",
    "d8": "Security runbook: rotate API keys every 90 days.",
}
QRELS = {
    "why did we drop kafka": {"d1": 2, "d5": 1},
    "E-4471": {"d2": 2, "d6": 1},
    "contractor leave": {"d4": 2, "d3": 1},
    "dead letter queue": {"d5": 2},
}


def ndcg_at_k(ranked_ids: list[str], rel: dict[str, int], k: int = 3) -> float:
    dcg = lambda g: sum(x / math.log2(i + 1) for i, x in enumerate(g, start=1))  # noqa: E731
    gains = [float(rel.get(d, 0)) for d in ranked_ids[:k]]
    ideal = sorted((float(v) for v in rel.values()), reverse=True)[:k]
    return dcg(gains) / dcg(ideal) if dcg(ideal) else 0.0


def part_c() -> None:
    print("\n== C. Toy hybrid run (illustrative only) ==")
    bm = BM25(CORPUS)
    vecs = {d: trigram_vec(t) for d, t in CORPUS.items()}
    print(f"{'query':<24}{'method':<10}{'nDCG@3':>8}   top-3")
    for q, rel in QRELS.items():
        lex_scores = dict(bm.rank(q))
        lex = [d for d, _ in sorted(lex_scores.items(), key=lambda x: (-x[1], x[0]))]
        qv = trigram_vec(q)
        den_scores = {d: cos(qv, v) for d, v in vecs.items()}
        den = [d for d, s in sorted(den_scores.items(), key=lambda x: (-x[1], x[0])) if s > 0]
        fused = order(rrf([lex[:8], den[:8]]))
        lin = order(linear_minmax(lex_scores, {d: den_scores[d] for d in den[:8]}))
        for name, lst in (("bm25", lex), ("dense*", den), ("rrf", fused), ("minmax", lin)):
            print(f"{q:<24}{name:<10}{ndcg_at_k(lst, rel):>8.2f}   {lst[:3]}")
    print("* character-trigram stand-in; not a real embedding model. 4 queries: no conclusions about hybrid search.")


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    print("\nAll assertions passed.")
