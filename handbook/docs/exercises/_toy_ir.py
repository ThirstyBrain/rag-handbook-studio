"""Shared toy retrieval helpers for the Chapter 10/11 exercises (stdlib only).

Not a library: just enough BM25, RRF and metrics to make query-transformation mechanics
visible. Everything here is deterministic. The 'stemmer' is deliberately trivial (plural -s)
so that morphology is not the variable under study.
"""
from __future__ import annotations

import math
import re
from collections import Counter

STOP = {"the", "a", "an", "of", "for", "to", "in", "is", "are", "and", "or", "it", "its", "be", "by",
        "what", "how", "who", "do", "does", "that", "this", "with", "on", "at", "from", "as", "i", "we", "can"}


def stem(t: str) -> str:
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def tokens(s: str, drop_stop: bool = True) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", s.lower())
    return [stem(t) for t in toks if not (drop_stop and t in STOP)]


class BM25:
    def __init__(self, docs: dict[str, str], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = {d: Counter(tokens(t)) for d, t in docs.items()}
        self.len = {d: max(1, sum(c.values())) for d, c in self.tf.items()}
        self.N = len(docs)
        self.avg = sum(self.len.values()) / self.N
        self.df: Counter[str] = Counter()
        for c in self.tf.values():
            self.df.update(c.keys())

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1.0 + (self.N - n + 0.5) / (n + 0.5))

    def score(self, weighted_terms: dict[str, float], doc: str) -> float:
        s = 0.0
        for t, w in weighted_terms.items():
            f = self.tf[doc].get(t, 0)
            if f:
                norm = 1.0 - self.b + self.b * self.len[doc] / self.avg
                s += w * self.idf(t) * f * (self.k1 + 1.0) / (f + self.k1 * norm)
        return s

    def search(self, query: str | dict[str, float], k: int = 10) -> list[tuple[str, float]]:
        wt = query if isinstance(query, dict) else dict(Counter(tokens(query)))
        sc = {d: self.score(wt, d) for d in self.tf}
        return [(d, s) for d, s in sorted(sc.items(), key=lambda x: (-x[1], x[0])) if s > 0][:k]


def weighted(original: str, expansion: list[str], w_exp: float) -> dict[str, float]:
    """Original terms weight 1.0; expansion terms weight w_exp (never lowers an original term)."""
    wt: dict[str, float] = {t: 1.0 for t in tokens(original)}
    for t in tokens(" ".join(expansion)):
        if t not in wt:                 # an expansion never overrides or lowers an original query term
            wt[t] = w_exp
    return wt


def rrf(lists: list[list[str]], k: int = 60, weights: list[float] | None = None) -> list[tuple[str, float]]:
    w = weights or [1.0] * len(lists)
    sc: dict[str, float] = {}
    for wi, lst in zip(w, lists, strict=True):
        for r, d in enumerate(lst, start=1):
            sc[d] = sc.get(d, 0.0) + wi / (k + r)
    return sorted(sc.items(), key=lambda kv: (-kv[1], kv[0]))


def ndcg_at_k(ranked_ids: list[str], rel: dict[str, int], k: int = 3) -> float:
    dcg = lambda g: sum(x / math.log2(i + 1) for i, x in enumerate(g, start=1))  # noqa: E731
    gains = [float(rel.get(d, 0)) for d in ranked_ids[:k]]
    ideal = sorted((float(v) for v in rel.values()), reverse=True)[:k]
    return dcg(gains) / dcg(ideal) if dcg(ideal) else 0.0


def recall_at_k(ranked_ids: list[str], rel: dict[str, int], k: int = 3) -> float:
    total = sum(1 for v in rel.values() if v > 0)
    return sum(1 for d in ranked_ids[:k] if rel.get(d, 0) > 0) / total if total else 0.0
