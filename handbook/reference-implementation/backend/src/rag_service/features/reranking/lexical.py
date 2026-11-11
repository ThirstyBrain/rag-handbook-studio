"""A local, dependency-free baseline reranker: BM25 over the candidate set only.

HONEST SCOPE: this is a lexical re-scoring of the few candidates retrieval already returned, with IDF taken
from those candidates. It is NOT a cross-encoder and does not understand meaning; it exists so the rerank
stage (port, guard, fallback, ordering, tests) is real and offline-capable ("local before cloud"). Whether it
improves ordering over first-stage fusion is unmeasured and must be judged on the golden set (component 17);
a cross-encoder or hosted reranker behind the same port is the intended upgrade (ADR-008 option D/B).
``k1`` and ``b`` are the conventional BM25 defaults, not tuned.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

from rag_service.features.reranking.ports import RerankItem

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class Bm25Reranker:
    name = "bm25-local"

    def __init__(self, k1: float = 1.2, b: float = 0.75) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("invalid BM25 parameters")
        self._k1, self._b = k1, b

    async def rerank(self, query: str, items: Sequence[RerankItem]) -> list[float]:
        docs = [tokenize(i.text) for i in items]
        if not docs:
            return []
        terms = set(tokenize(query))
        n = len(docs)
        avg_len = (sum(len(d) for d in docs) / n) or 1.0
        df = {t: sum(1 for d in docs if t in d) for t in terms}
        scores: list[float] = []
        for doc in docs:
            counts = Counter(doc)
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf == 0:
                    continue
                idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
                norm = tf + self._k1 * (1 - self._b + self._b * len(doc) / avg_len)
                score += idf * tf * (self._k1 + 1) / norm
            scores.append(score)
        return scores
