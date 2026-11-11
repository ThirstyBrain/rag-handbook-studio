"""Mutation check for the database-free parts of retrieval (components 6-8): RRF fusion, query validation,
the filter compiler, the index DDL generator and the search service's degradation logic.

Same method and runner as mutation_extract.py: one realistic defect per mutant, the unit tests must FAIL,
the file is always restored. These tests need NO database. The SQL itself is not covered by any mutant
here (it needs PostgreSQL). Run from reference-implementation/backend:
    python ../scripts/mutation_retrieval.py [description-filter]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutation_extract as mx

R = mx.FEATURES / "retrieval"
I = mx.FEATURES / "indexing"  # noqa: E741
RR = mx.FEATURES / "reranking"
UNIT = [
    "../tests/unit/test_retrieval.py",
    "../tests/unit/test_filters.py",
    "../tests/unit/test_index_ddl.py",
    "../tests/unit/test_reranking.py",
]

MUTANTS: list[mx.Mutant] = [
    # ---------------------------------------------------------------- fusion
    (R / "fusion.py", "k + position", "k - position", "rank damping sign flipped", UNIT),
    (R / "fusion.py", "if k < 1:", "if False:", "k not validated", UNIT),
    (R / "fusion.py", "if limit < 1:", "if False:", "limit not validated", UNIT),
    (R / "fusion.py", "if weight < 0:", "if False:", "negative weights accepted", UNIT),
    (R / "fusion.py", "if name in seen:", "if False:", "duplicates in one leg counted twice", UNIT),
    (R / "fusion.py", "weights.get(name, 1.0)", "1.0", "weights ignored", UNIT),
    (
        R / "fusion.py",
        "(-scores[cid], str(cid))",
        "(-scores[cid],)",
        "ties not broken deterministically",
        UNIT,
    ),
    (
        R / "fusion.py",
        "(-scores[cid], str(cid))",
        "(scores[cid], str(cid))",
        "ascending instead of descending",
        UNIT,
    ),
    (R / "fusion.py", "ordered[:limit]", "ordered", "limit not applied", UNIT),
    # ---------------------------------------------------------------- query validation
    (R / "query.py", "if not cleaned:", "if False:", "empty query accepted", UNIT),
    (
        R / "query.py",
        "if len(cleaned) > MAX_QUERY_CHARS:",
        "if False:",
        "oversize query accepted",
        UNIT,
    ),
    (
        R / "query.py",
        'ch not in "\\t\\n\\r"',
        "True",
        "tabs and newlines rejected as control characters",
        UNIT,
    ),
    (R / "query.py", "ord(ch) < 32 and", "False and", "control characters accepted", UNIT),
    (
        R / "query.py",
        "if not all(math.isfinite(x) for x in vector):",
        "if False:",
        "non-finite query vector accepted",
        UNIT,
    ),
    (R / "query.py", "if not any(vector):", "if False:", "zero query vector accepted", UNIT),
    (R / "query.py", "or len(vector) != dimensions", "", "query vector length not checked", UNIT),
    (
        R / "query.py",
        "1 <= dimensions <= max_dimensions",
        "1 <= dimensions",
        "dimension cap ignored",
        UNIT,
    ),
    # ---------------------------------------------------------------- filter compiler
    (
        R / "filters.py",
        "if spec is None or cond.op not in spec.ops:",
        "if spec is None:",
        "operator allow-list ignored",
        UNIT,
    ),
    (
        R / "filters.py",
        "if (cond.field, cond.op) in seen:",
        "if False:",
        "duplicate conditions accepted",
        UNIT,
    ),
    (
        R / "filters.py",
        "if len(conditions) > MAX_CONDITIONS:",
        "if False:",
        "condition count unbounded",
        UNIT,
    ),
    (
        R / "filters.py",
        "<= len(cond.value) <= MAX_IN_VALUES",
        "<= len(cond.value)",
        "'in' list unbounded",
        UNIT,
    ),
    (
        R / "filters.py",
        "1 <= len(cond.value)",
        "0 <= len(cond.value)",
        "empty 'in' list accepted",
        UNIT,
    ),
    (
        R / "filters.py",
        "if len(raw) > MAX_TEXT_CHARS:",
        "if False:",
        "oversize value accepted",
        UNIT,
    ),
    (R / "filters.py", "if parsed.tzinfo is None:", "if False:", "naive timestamp accepted", UNIT),
    (
        R / "filters.py",
        "if raw not in CLASSIFICATIONS:",
        "if False:",
        "classification not validated",
        UNIT,
    ),
    (R / "filters.py", 'if "\\x00" in raw:', "if False:", "NUL accepted", UNIT),
    (
        R / "filters.py",
        "if not isinstance(cond.value, str):",
        "if False:",
        "list accepted for a scalar operator",
        UNIT,
    ),
    (
        R / "filters.py",
        'clauses.append(f"{spec.column} >= %s")',
        'clauses.append(f"{spec.column} > %s")',
        "gte compiled as gt",
        UNIT,
    ),
    (
        R / "filters.py",
        'clauses.append(f"{spec.column} <= %s")',
        'clauses.append(f"{spec.column} < %s")',
        "lte compiled as lt",
        UNIT,
    ),
    (
        R / "filters.py",
        '"".join(f" AND ({c})" for c in clauses)',
        '"".join(f" OR ({c})" for c in clauses)',
        "conditions OR-ed instead of AND-ed",
        UNIT,
    ),
    (
        R / "filters.py",
        '"d.classification"',
        '"d.status"',
        "field mapped to the wrong column",
        UNIT,
    ),
    # ---------------------------------------------------------------- index DDL
    (
        I / "ddl.py",
        "if not SPACE_PATTERN.fullmatch(self.space):",
        "if False:",
        "space name not validated",
        UNIT,
    ),
    (
        I / "ddl.py",
        "<= MAX_VECTOR_DIMENSIONS",
        "<= MAX_VECTOR_DIMENSIONS + 1",
        "vector/halfvec boundary off by one",
        UNIT,
    ),
    (
        I / "ddl.py",
        "if not (self.m * 2 <= self.ef_construction <= 1000):",
        "if False:",
        "ef_construction not validated",
        UNIT,
    ),
    (
        I / "ddl.py",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS",
        "CREATE INDEX IF NOT EXISTS",
        "index build blocks writes",
        UNIT,
    ),
    (
        I / "ddl.py",
        "WHERE embedding_space = '{self.space}' AND dimensions",
        "WHERE dimensions",
        "index not partial on the space",
        UNIT,
    ),
    (
        I / "ddl.py",
        '"cosine": ("cosine_ops", "<=>")',
        '"cosine": ("cosine_ops", "<->")',
        "cosine mapped to the L2 operator",
        UNIT,
    ),
    # ---------------------------------------------------------------- search service
    (
        R / "service.py",
        "if not 1 <= top_k <= self._config.max_top_k:",
        "if False:",
        "top_k unbounded",
        UNIT,
    ),
    (
        R / "service.py",
        "flt = compile_filters(filters)",
        "flt = compile_filters(())",
        "filters dropped",
        UNIT,
    ),
    (
        R / "service.py",
        "if len(result.vectors) != 1:",
        "if False:",
        "wrong number of query vectors accepted",
        UNIT,
    ),
    (
        R / "service.py",
        "validate_query_vector(vector, result.dimensions, cfg.max_dimensions)",
        "pass",
        "query vector not validated",
        UNIT,
    ),
    (
        R / "service.py",
        "except TimeoutError:",
        "except KeyboardInterrupt:",
        "embedding timeout not handled",
        UNIT,
    ),
    (
        R / "service.py",
        "except LlmError as exc:",
        "except KeyError as exc:",
        "provider errors not degraded",
        UNIT,
    ),
    (
        R / "service.py",
        'return None, None, ["vector:not_configured"]',
        "return None, None, []",
        "missing gateway not reported",
        UNIT,
    ),
    (
        R / "service.py",
        "ef_search=cfg.ef_search, iterative_scan=cfg.iterative_scan, flt=flt,",
        "ef_search=cfg.ef_search, iterative_scan=cfg.iterative_scan,",
        "filter not applied to the vector leg",
        UNIT,
    ),
    (
        R / "service.py",
        "fts_candidates(conn, text, cfg.candidates_per_leg, flt)",
        "fts_candidates(conn, text, cfg.candidates_per_leg)",
        "filter not applied to the lexical leg",
        UNIT,
    ),
    (
        R / "service.py",
        '"hits": len(hits),',
        '"hits": len(hits), "query": text,',
        "query text leaked into events",
        UNIT,
    ),
    # ---------------------------------------------------------------- reranking (component 9)
    # Equivalent mutants deliberately NOT listed: dropping `if tf == 0: continue` (a zero term frequency
    # adds 0) and dropping the explicit tie index in apply_scores (Python's sort is stable, so ties keep
    # their order anyway).
    (
        RR / "lexical.py",
        "if k1 <= 0 or not 0 <= b <= 1:",
        "if False:",
        "BM25 parameters not validated",
        UNIT,
    ),
    (
        RR / "lexical.py",
        "(n - df[term] + 0.5) / (df[term] + 0.5)",
        "(n + 0.5) / (df[term] + 0.5)",
        "idf ignores document frequency of the rest",
        UNIT,
    ),
    (RR / "lexical.py", "self._b * len(doc) / avg_len", "0", "no length normalisation", UNIT),
    (
        RR / "apply.py",
        "key=lambda i: (-scores[i], i)",
        "key=lambda i: (scores[i], i)",
        "ascending instead of descending",
        UNIT,
    ),
    (RR / "apply.py", "for i in order[:limit]", "for i in order", "limit not applied", UNIT),
    (RR / "apply.py", "if len(hits) != len(scores):", "if False:", "score count not checked", UNIT),
    (
        RR / "apply.py",
        '"first_stage": i + 1',
        '"first_stage": i',
        "first-stage position off by one",
        UNIT,
    ),
    (
        RR / "guard.py",
        "if not self._breaker.allow():",
        "if False:",
        "open breaker still calls the reranker",
        UNIT,
    ),
    (RR / "guard.py", "if len(scores) != expected or", "if", "score count not validated", UNIT),
    (
        RR / "guard.py",
        "not all(math.isfinite(s) for s in scores)",
        "False",
        "non-finite scores accepted",
        UNIT,
    ),
    (
        RR / "guard.py",
        "        self._breaker.success()\n",
        "        pass\n",
        "breaker never closes after success",
        UNIT,
    ),
    (
        RR / "guard.py",
        'return None, "rerank:timeout"',
        "return scores, None",
        "timeout not reported",
        UNIT,
    ),
    (RR / "guard.py", "if not items:", "if False:", "empty input still calls the reranker", UNIT),
    (RR / "guard.py", "if timeout_s <= 0:", "if False:", "timeout not validated", UNIT),
    (
        R / "service.py",
        "limit=max(top_k, cfg.rerank_candidates) if self._reranker else top_k,",
        "limit=top_k,",
        "reranker sees only top_k candidates",
        UNIT,
    ),
    (
        R / "service.py",
        "hits, reranked = apply_scores(fused, scores, top_k), True",
        "hits, reranked = fused[:top_k], True",
        "reranker scores ignored",
        UNIT,
    ),
    (
        R / "service.py",
        "degraded = [*degraded, reason]",
        "pass",
        "rerank fallback not reported",
        UNIT,
    ),
]


if __name__ == "__main__":
    mx.UNIT, mx.DB, mx.MUTANTS = UNIT, [], MUTANTS
    raise SystemExit(mx.main())
