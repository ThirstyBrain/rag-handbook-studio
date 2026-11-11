"""Chapter 18 exercise: an evaluation harness you can trust (stdlib only).

What it demonstrates, with executed assertions:
  A. retrieval metrics (hit, recall@k, precision@k, MRR, nDCG@k) with hand-computed expectations and edge cases;
  B. a rank-aware context-precision metric (Ragas formula, S140) versus plain precision@k;
  C. claim-level faithfulness (supported claims / claims, S135) and citation checks, using a deliberately
     WEAK lexical verifier so its failure modes are visible (a real system needs an NLI/LLM judge, which
     must itself be validated: part D);
  D. judge validation: raw agreement vs Cohen's kappa, and position bias with order-balanced aggregation (S141);
  E. statistics: paired bootstrap confidence interval, a regression gate, and how often it fires at
     different golden-set sizes (SIMULATION with synthetic scores: illustrative, not a measurement of any RAG system);
  F. slice reporting: an aggregate that improves while one slice regresses;
  G. a mutation check of the metric code itself.

Run: python -I docs/exercises/ch18_evaluation.py [--mutants]
Everything is deterministic (seeded). Data are constructed for teaching; no real system, model or corpus.
"""
from __future__ import annotations

import math
import random
import re
import sys

MUT: set[str] = set()  # injected defects, used only by the mutation check in part G


# ---------------------------------------------------------------- A. retrieval metrics
def _dedupe(ranked: list[str]) -> list[str]:
    """A chunk retrieved twice is one result: the first occurrence counts."""
    if "no-dedupe" in MUT:
        return list(ranked)
    seen: set[str] = set()
    out = []
    for d in ranked:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _relevant(rel: dict[str, int]) -> set[str]:
    return {d for d, g in rel.items() if g > 0}


def hit_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    return 1.0 if any(rel.get(d, 0) > 0 for d in _dedupe(ranked)[:k]) else 0.0


def recall_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    rs = _relevant(rel)
    if not rs:  # a query nobody can answer from the corpus is a golden-set defect, not a score of 0 or 1
        raise ValueError("query has no relevant documents: fix or exclude it")
    top = _dedupe(ranked)[:k]
    denom = len(top) if "recall-denominator-retrieved" in MUT else len(rs)
    return sum(1 for d in top if d in rs) / denom if denom else 0.0


def precision_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    top = _dedupe(ranked)[:k]
    denom = (len(top) or 1) if "precision-short-list" in MUT else k  # a short list is penalised
    return sum(1 for d in top if rel.get(d, 0) > 0) / denom


def mrr(ranked: list[str], rel: dict[str, int]) -> float:
    for r, d in enumerate(_dedupe(ranked), start=1):
        if rel.get(d, 0) > 0:
            return 1.0 / (r + 1 if "mrr-offset" in MUT else r)
    return 0.0


def ndcg_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    shift = 2 if "ndcg-log-offset" in MUT else 1
    dcg = lambda gs: sum(g / math.log2(i + shift) for i, g in enumerate(gs, start=1))  # noqa: E731
    top = _dedupe(ranked)[:k]
    gains = [float(rel.get(d, 0)) for d in top]
    pool = gains if "ndcg-ideal-from-retrieved" in MUT else [float(v) for v in rel.values()]
    ideal = sorted(pool, reverse=True)[:k]  # the ideal ranking is over ALL judged documents
    return dcg(gains) / dcg(ideal) if dcg(ideal) else 0.0


# ---------------------------------------------------------------- B. rank-aware context precision
def context_precision(flags: list[bool]) -> float:
    """Ragas-style Context Precision@K: sum(precision@k * v_k) / (relevant items in top K) (S140)."""
    relevant_total = sum(flags)
    if relevant_total == 0:
        return 0.0
    acc, hits = 0.0, 0
    for k, v in enumerate(flags, start=1):
        if v:
            hits += 1
            acc += hits / k
    return acc / relevant_total


# ---------------------------------------------------------------- C. faithfulness and citations (weak stand-in verifier)
_STOP = {"the", "a", "an", "was", "is", "are", "in", "on", "of", "to", "and", "does", "do", "for", "by", "at"}


def _toks(s: str) -> set[str]:
    out = set()
    for t in re.findall(r"[a-z0-9]+", s.lower()):
        if t not in _STOP:
            out.add(t[:-1] if len(t) > 3 and t.endswith("s") else t)
    return out


def supported(claim: str, contexts: list[str]) -> bool:
    """STAND-IN verifier: every content word of the claim appears in ONE context chunk. It is cheap,
    deterministic and wrong in known ways (paraphrase, negation); see demo_verifier_failures()."""
    if "union-of-contexts" in MUT:  # lets a claim be stitched together from different chunks
        return _toks(claim) <= set().union(*(_toks(c) for c in contexts))
    return any(_toks(claim) <= _toks(c) for c in contexts)


def faithfulness(claims: list[str], contexts: list[str]) -> float | None:
    """Supported claims / all claims. An answer with no claims has no faithfulness score (not 1.0)."""
    if not claims:
        return 1.0 if "empty-answer-is-faithful" in MUT else None
    return sum(supported(c, contexts) for c in claims) / len(claims)


def citation_report(answer: list[tuple[str, list[str]]], retrieved: dict[str, str]) -> dict[str, int]:
    """answer: (claim, cited chunk ids). Phantom = cites an id that was never retrieved (fabricated);
    unsupported = cites a real chunk that does not support the claim; uncited = no citation at all."""
    phantom = unsupported = uncited = 0
    for claim, ids in answer:
        if not ids:
            uncited += 1
            continue
        for cid in ids:
            if cid not in retrieved:
                if "skip-phantom-check" not in MUT:
                    phantom += 1
                continue
            if not supported(claim, [retrieved[cid]]):
                unsupported += 1
    return {"phantom": phantom, "unsupported": unsupported, "uncited": uncited}


# ---------------------------------------------------------------- D. judge validation
def agreement_and_kappa(judge: list[bool], human: list[bool]) -> tuple[float, float]:
    n = len(judge)
    po = sum(j == h for j, h in zip(judge, human, strict=True)) / n
    if "kappa-no-chance-correction" in MUT:
        return po, po
    pj, ph = sum(judge) / n, sum(human) / n
    pe = pj * ph + (1 - pj) * (1 - ph)
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0


def pairwise_judge(qa: float, qb: float, rng: random.Random, first_bonus: float) -> str:
    """STAND-IN judge: noisy view of latent quality plus a bonus for whichever answer is shown first."""
    a = qa + rng.gauss(0, 0.1) + first_bonus
    b = qb + rng.gauss(0, 0.1)
    return "first" if a > b else "second"


def balanced_verdict(qa: float, qb: float, rng: random.Random, first_bonus: float) -> str:
    """Judge both orders; count a win only if it survives the swap, otherwise call it a tie."""
    one = pairwise_judge(qa, qb, rng, first_bonus)  # A shown first
    two = pairwise_judge(qb, qa, rng, first_bonus)  # B shown first
    a_wins_1, a_wins_2 = one == "first", two == "second"
    if "single-order-only" in MUT:
        return "A" if a_wins_1 else "B"
    if a_wins_1 and a_wins_2:
        return "A"
    if not a_wins_1 and not a_wins_2:
        return "B"
    return "tie"


# ---------------------------------------------------------------- E. statistics
def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def bootstrap_ci(values: list[float], rng: random.Random, b: int = 400, alpha: float = 0.05) -> tuple[float, float]:
    n = len(values)
    means = sorted(mean(rng.choices(values, k=n)) for _ in range(b))
    return means[int(b * alpha / 2)], means[int(b * (1 - alpha / 2)) - 1]


def paired_delta_ci(old: list[float], new: list[float], rng: random.Random, b: int = 400) -> tuple[float, float]:
    """Resample QUERIES, keep each query's (old, new) pair together: queries differ far more than systems do."""
    n = len(old)
    deltas = []
    for _ in range(b):
        idx = rng.choices(range(n), k=n)
        j = rng.choices(range(n), k=n) if "paired-broken" in MUT else idx
        deltas.append(mean([new[i] for i in idx]) - mean([old[i] for i in j]))
    deltas.sort()
    return deltas[int(b * 0.025)], deltas[int(b * 0.975) - 1]


def verdict(old: list[float], new: list[float], rng: random.Random, b: int = 400) -> str:
    lo, hi = paired_delta_ci(old, new, rng, b)
    if "gate-uses-point-estimate" in MUT:
        return "regression" if mean(new) < mean(old) else "ok"
    return "regression" if hi < 0 else ("improvement" if lo > 0 else "inconclusive")


def simulate(n: int, true_delta: float, rng: random.Random) -> tuple[list[float], list[float]]:
    # Unbounded synthetic scores on purpose: clipping to [0, 1] would bias a "no change" system downward
    # (found while writing this exercise: it produced a 17% "false alarm" that was really a real shift).
    old = [rng.gauss(0.6, 0.25) for _ in range(n)]
    new = [s + true_delta + rng.gauss(0, 0.15) for s in old]
    return old, new


def detection_rate(n: int, true_delta: float, trials: int, seed: int) -> float:
    rng = random.Random(seed)
    hits = sum(verdict(*simulate(n, true_delta, rng), rng, b=200) == "regression" for _ in range(trials))
    return hits / trials


# ---------------------------------------------------------------- F. slices
def by_slice(rows: list[tuple[str, float]]) -> dict[str, float]:
    groups: dict[str, list[float]] = {}
    for s, v in rows:
        groups.setdefault(s, []).append(v)
    return {s: mean(v) for s, v in groups.items()}


# ---------------------------------------------------------------- checks
def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def check_retrieval() -> None:
    rel = {"d1": 2, "d2": 1, "d3": 0, "d4": 1}  # graded judgments; 3 relevant
    ranked = ["d3", "d1", "d9", "d2", "d1"]  # d1 appears twice
    assert hit_at_k(ranked, rel, 1) == 0.0 and hit_at_k(ranked, rel, 2) == 1.0
    assert approx(recall_at_k(ranked, rel, 5), 2 / 3), "d1 counts once; d4 never retrieved"
    assert approx(precision_at_k(ranked, rel, 5), 2 / 5), "denominator is k even if fewer are returned"
    assert approx(precision_at_k(["d1"], rel, 4), 1 / 4), "a short list is penalised"
    assert approx(mrr(ranked, rel), 1 / 2)
    assert mrr(["d3", "d9"], rel) == 0.0
    # nDCG@3: dedupe -> [d3, d1, d9] gains [0,2,0]; DCG = 2/log2(3); ideal [2,1,1] = 2 + 1/log2(3) + 1/2
    dcg = 2 / math.log2(3)
    ideal = 2 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert approx(ndcg_at_k(ranked, rel, 3), dcg / ideal)
    assert approx(ndcg_at_k(["d1", "d2", "d4"], rel, 3), 1.0)
    assert ndcg_at_k(["d3"], {"d3": 0}, 3) == 0.0, "no ideal gain: defined as 0, not a crash"
    try:
        recall_at_k(["d1"], {"d1": 0}, 3)
        raise AssertionError("a query with no relevant docs must be rejected")
    except ValueError:
        pass
    # relevant document outside the top-k: invisible to recall@k but found at larger k
    far = ["x1", "x2", "x3", "d1"]
    assert recall_at_k(far, {"d1": 1}, 3) == 0.0 and recall_at_k(far, {"d1": 1}, 4) == 1.0


def check_context_precision() -> None:
    assert approx(context_precision([True, True, False]), 1.0)
    assert approx(context_precision([False, True, True]), (1 / 2 + 2 / 3) / 2)
    assert context_precision([False, False]) == 0.0
    assert context_precision([True, False, False]) == 1.0, "extra irrelevant chunks AFTER the hit do not hurt"
    assert approx(precision_at_k(["a", "b", "c"], {"a": 1, "b": 1}, 3), 2 / 3)
    # rank-aware: same set of chunks, relevant ones last -> lower context precision, identical precision@3
    assert context_precision([False, True, True]) < context_precision([True, True, False])
    assert approx(precision_at_k(["n", "a", "b"], {"a": 1, "b": 1}, 3), precision_at_k(["a", "b", "n"], {"a": 1, "b": 1}, 3))


def check_faithfulness_and_citations() -> None:
    ctx = ["Einstein was born in Germany on 14 March 1879"]
    claims = ["Einstein was born in Germany", "Einstein was born on 20 March 1879"]
    assert faithfulness(claims, ctx) == 0.5, "the documented worked example: one of two claims supported"
    assert faithfulness([], ctx) is None, "no claims: no score (an empty answer is not perfectly faithful)"
    stitched = ["Alice leads Berlin office", "Bob manages budget"]
    assert supported("Alice manages budget", stitched) is False, "a claim may not be stitched from two chunks"
    retrieved = {"c1": "Refunds are issued within 14 days", "c2": "Shipping takes 3 days"}
    rep = citation_report(
        [("Refunds are issued within 14 days", ["c1"]), ("Refunds are issued within 30 days", ["c1"]),
         ("Shipping takes 3 days", ["c9"]), ("Support is open daily", [])], retrieved)
    assert rep == {"phantom": 1, "unsupported": 1, "uncited": 1}, rep


def demo_verifier_failures() -> None:
    """Why a cheap verifier cannot be the final judge: it fails in BOTH directions."""
    paraphrase = supported("The physicist first drew breath in Germany", ["Einstein was born in Germany"])
    contradiction = supported("The policy allows remote work", ["The policy does not allow remote work"])
    assert paraphrase is False, "false negative: a true paraphrase is called unsupported"
    assert contradiction is True, "false positive: a contradicted claim is called supported"
    print("verifier failures (constructed): paraphrase ->", paraphrase, "| negation ->", contradiction)


def check_judge_validation() -> None:
    # 90% of answers are faithful; a judge that always says "faithful" agrees 90% of the time with humans
    human = [True] * 90 + [False] * 10
    lazy = [True] * 100
    po, kappa = agreement_and_kappa(lazy, human)
    assert approx(po, 0.9) and approx(kappa, 0.0), (po, kappa)
    perfect = agreement_and_kappa(human, human)
    assert approx(perfect[0], 1.0) and approx(perfect[1], 1.0)
    # position bias: human says the two answers are EQUAL quality (identical latent quality)
    rng = random.Random(7)
    n = 400
    single_first = sum(pairwise_judge(0.5, 0.5, rng, 0.1) == "first" for _ in range(n)) / n
    verdicts = [balanced_verdict(0.5, 0.5, rng, 0.1) for _ in range(n)]
    ties = verdicts.count("tie") / n
    assert single_first > 0.65, f"the biased judge prefers whichever answer is shown first: {single_first:.2f}"
    assert ties > 0.5, f"order-balanced aggregation turns bias-driven wins into ties: {ties:.2f}"
    # and it still recognises a real quality gap
    real = [balanced_verdict(0.9, 0.3, rng, 0.1) for _ in range(200)]
    assert real.count("A") / 200 > 0.95
    print(f"position bias (equal-quality pairs): single-order first-wins {single_first:.2f}; "
          f"balanced ties {ties:.2f}; real gap recognised {real.count('A') / 200:.2f}")


def check_statistics() -> dict[str, float]:
    rng = random.Random(11)
    old, new = simulate(300, -0.03, rng)
    lo, hi = paired_delta_ci(old, new, random.Random(1))
    # unpaired intervals: resample each system independently -> wider because query difficulty is not cancelled
    unpaired_diffs = sorted(mean(random.Random(i).choices(new, k=300)) - mean(random.Random(i + 999).choices(old, k=300))
                            for i in range(400))
    paired_w, unpaired_w = hi - lo, unpaired_diffs[389] - unpaired_diffs[10]
    assert paired_w < 0.5 * unpaired_w, (paired_w, unpaired_w)  # pairing cancels query difficulty
    # a pure-noise change is not called a regression, and a clear one is
    n_old, n_new = simulate(400, 0.0, random.Random(5))
    assert verdict(n_old, n_new, random.Random(2)) in {"inconclusive", "improvement", "regression"}
    big_old, big_new = simulate(400, -0.10, random.Random(6))
    assert verdict(big_old, big_new, random.Random(2)) == "regression"
    # the same -0.03 regression: how often does the gate see it as the golden set grows?
    rates = {n: detection_rate(n, -0.03, trials=60, seed=100 + n) for n in (30, 100, 400, 1600)}
    false_alarm = detection_rate(400, 0.0, trials=60, seed=777)
    assert rates[30] < rates[1600] and rates[400] >= 0.9, rates
    assert rates[30] <= 0.35, f"with 30 queries the gate rarely sees a 3-point regression: {rates[30]:.2f}"
    assert false_alarm <= 0.15, false_alarm
    print("regression of -0.03 detected at n=30/100/400/1600:", {n: round(r, 2) for n, r in rates.items()},
          "| false alarms at no change (n=400):", round(false_alarm, 2))
    return {"paired_width": paired_w, "unpaired_width": unpaired_w}


def check_slices() -> None:
    old = [("en", 0.80)] * 90 + [("de", 0.70)] * 10
    new = [("en", 0.84)] * 90 + [("de", 0.40)] * 10
    agg_old, agg_new = mean([v for _, v in old]), mean([v for _, v in new])
    assert agg_new > agg_old, "the aggregate improves ..."
    so, sn = by_slice(old), by_slice(new)
    assert sn["de"] < so["de"] - 0.25 and sn["en"] > so["en"], "... while one slice collapses"
    print(f"slice view: aggregate {agg_old:.3f} -> {agg_new:.3f}; de slice {so['de']:.2f} -> {sn['de']:.2f}")


def run_checks() -> None:
    check_retrieval()
    check_context_precision()
    check_faithfulness_and_citations()
    check_judge_validation()
    check_slices()
    check_statistics()


def main() -> None:
    run_checks()
    demo_verifier_failures()
    print("OK: all assertions hold (constructed data and synthetic simulation; no real RAG system measured).")


MUTANT_NAMES = [
    "no-dedupe", "recall-denominator-retrieved", "precision-short-list", "mrr-offset", "ndcg-log-offset",
    "ndcg-ideal-from-retrieved", "union-of-contexts", "empty-answer-is-faithful", "skip-phantom-check",
    "kappa-no-chance-correction", "single-order-only", "paired-broken", "gate-uses-point-estimate",
]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except (AssertionError, ValueError, ZeroDivisionError):
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
