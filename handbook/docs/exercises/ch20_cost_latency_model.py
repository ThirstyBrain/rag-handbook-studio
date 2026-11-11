"""Chapter 20 exercise: the arithmetic behind RAG cost, storage and tail latency (stdlib only).

  A. token and cost model for one query: how k and chunk size drive input tokens; prompt-caching economics
     for the static prefix (multipliers as documented by one vendor, S152; they are model-specific) and the
     hit probability a given request rate can sustain;
  B. raw vector storage by type (pgvector's documented bytes per dimension, S143) and what that does NOT include;
  C. tail latency: fan-out amplification 1-(1-p)^n checked by simulation, a hedged-request simulation, why
     percentiles do not add, and Little's law for pool sizing;
  D. a mutation check of the formulas.

Run: python -I docs/exercises/ch20_cost_latency_model.py [--mutants]
PRICES ARE ABSTRACT UNITS (per million tokens), not any vendor's price list. Latencies are simulated draws from
assumed distributions. Nothing here measures a real system; the measured pgvector numbers are in
reference-implementation/evaluation/bench_pgvector.py.
"""
from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass

MUT: set[str] = set()


# ---------------------------------------------------------------- A. tokens and cost
@dataclass(frozen=True)
class QueryShape:
    system_tokens: int      # static instructions (cacheable prefix)
    question_tokens: int
    k: int                  # chunks placed in the prompt
    chunk_tokens: int
    chunk_overhead: int     # wrapper per chunk (delimiters, source id)
    output_tokens: int


def input_tokens(q: QueryShape) -> int:
    return q.system_tokens + q.question_tokens + q.k * (q.chunk_tokens + q.chunk_overhead)


def query_cost(q: QueryShape, price_in: float, price_out: float, *, prefix_multiplier: float = 1.0) -> float:
    """Cost in price units. `prefix_multiplier` scales the static system prefix (1.0 = uncached)."""
    variable = input_tokens(q) - q.system_tokens
    return (q.system_tokens * prefix_multiplier * price_in + variable * price_in + q.output_tokens * price_out) / 1e6


def expected_prefix_multiplier(hit_probability: float, write_mult: float, read_mult: float) -> float:
    """Average multiplier on the cached prefix: a hit pays the read rate, a miss pays the write rate."""
    if "read-uses-write-mult" in MUT:
        return hit_probability * write_mult + (1 - hit_probability) * write_mult
    return hit_probability * read_mult + (1 - hit_probability) * write_mult


def cache_break_even(write_mult: float, read_mult: float) -> float:
    """Smallest hit probability at which caching the prefix costs less than not caching it."""
    if "break-even-wrong" in MUT:
        return (write_mult - 1) / write_mult
    return (write_mult - 1) / (write_mult - read_mult)


def hit_probability(requests_per_min: float, ttl_min: float) -> float:
    """P(the next request arrives before the cache entry expires), Poisson arrivals, TTL refreshed on every use."""
    return 1 - math.exp(-requests_per_min * ttl_min)


def simulate_hit_rate(rate: float, ttl: float, n: int, seed: int) -> float:
    rng = random.Random(seed)
    hits = sum(rng.expovariate(rate) < ttl for _ in range(n))
    return hits / n


# ---------------------------------------------------------------- B. storage
def vector_bytes(dim: int, kind: str) -> int:
    """Bytes per stored vector according to the pgvector README: type payload + 8 bytes (S143)."""
    if kind == "vector":
        return 4 * dim + 8
    if kind == "halfvec":
        return (4 if "halfvec-as-float32" in MUT else 2) * dim + 8
    if kind == "bit":
        return math.ceil(dim / (16 if "bit-bytes-wrong" in MUT else 8)) + 8
    raise ValueError(kind)


# ---------------------------------------------------------------- C. tail latency
def p_any_slow(n: int, p: float) -> float:
    """Probability that at least one of n independent calls is slower than its own p-th-tail threshold."""
    if "fanout-linear" in MUT:
        return min(1.0, n * p)
    return 1 - (1 - p) ** n


def call_latency(rng: random.Random) -> float:
    """Assumed single-call latency in ms: lognormal body (median 100 ms) plus a 1% chance of a 1,000 ms stall."""
    base = rng.lognormvariate(math.log(100), 0.3)
    return base + (1000.0 if rng.random() < 0.01 else 0.0)


def pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


def hedged_latency(rng: random.Random, delay_ms: float) -> tuple[float, bool]:
    """Send a second copy if the first has not finished after delay_ms; the earlier completion wins."""
    first = call_latency(rng)
    if "hedge-immediately" in MUT:
        delay_ms = 0.0
    if first <= delay_ms:
        return first, False
    return min(first, delay_ms + call_latency(rng)), True


def littles_law(arrival_rate_per_s: float, latency_s: float) -> float:
    """Average number of requests in flight = arrival rate x time in system."""
    return arrival_rate_per_s * (latency_s + (1.0 if "littles-law-wrong" in MUT else 0.0))


# ---------------------------------------------------------------- checks
def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def check_cost() -> dict[str, float]:
    q = QueryShape(system_tokens=800, question_tokens=40, k=8, chunk_tokens=400, chunk_overhead=20, output_tokens=300)
    assert input_tokens(q) == 800 + 40 + 8 * 420
    base = query_cost(q, 1.0, 5.0)
    k16 = query_cost(QueryShape(**{**q.__dict__, "k": 16}), 1.0, 5.0)
    assert k16 > base
    delta_in = (query_cost(QueryShape(**{**q.__dict__, "k": 16}), 1.0, 0.0) - query_cost(q, 1.0, 0.0)) * 1e6
    assert approx(delta_in, 8 * 420), "each extra chunk adds exactly its tokens to the input bill"
    # output tokens cost more per token: shortening answers can matter as much as shrinking context
    out_share = q.output_tokens * 5.0 / (input_tokens(q) * 1.0 + q.output_tokens * 5.0)
    assert 0.2 < out_share < 0.3, out_share
    # prefix caching: only the static system prompt is cacheable; retrieved chunks differ per query
    write, read = 1.25, 0.1  # one vendor's documented 5-minute-TTL multipliers (S152); model-specific
    assert approx(cache_break_even(write, read), 0.25 / 1.15)
    assert expected_prefix_multiplier(1.0, write, read) == read and expected_prefix_multiplier(0.0, write, read) == write
    h = 0.9
    cached = query_cost(q, 1.0, 5.0, prefix_multiplier=expected_prefix_multiplier(h, write, read))
    saving = 1 - cached / base
    mult = h * read + (1 - h) * write  # 0.215
    # analytic: only the 800-token prefix is discounted; total = 4,200 input + 300 x 5 output = 5,700 token-units
    assert approx(saving, 800 * (1 - mult) / 5700, 1e-9), saving
    assert saving < 0.12, "retrieved chunks and output dominate this prompt, so prefix caching saves ~11%"
    big_prefix = QueryShape(**{**q.__dict__, "system_tokens": 6000})
    saving_big = 1 - query_cost(big_prefix, 1.0, 5.0, prefix_multiplier=expected_prefix_multiplier(h, write, read)) / query_cost(big_prefix, 1.0, 5.0)
    assert saving_big > 2 * saving, (saving, saving_big)
    # hit probability from request rate (Poisson assumption), checked by simulation
    for rate, ttl in ((0.1, 5.0), (0.5, 5.0), (2.0, 5.0)):
        assert abs(hit_probability(rate, ttl) - simulate_hit_rate(rate, ttl, 40_000, 3)) < 0.01
    assert hit_probability(0.1, 5.0) < cache_break_even(write, read) + 0.4  # ~0.39: barely above break-even
    return {"saving_small_prefix": saving, "saving_big_prefix": saving_big, "hit_at_0.1_per_min": hit_probability(0.1, 5.0)}


def check_storage() -> dict[str, int]:
    n, d = 1_000_000, 1536
    v, h, b = (n * vector_bytes(d, kind) for kind in ("vector", "halfvec", "bit"))
    assert v == 6_152_000_000 and h == 3_080_000_000 and b == 200_000_000, (v, h, b)
    assert 1.99 < v / h < 2.01 and 30 < v / b < 31
    assert vector_bytes(1024, "bit") == 128 + 8
    return {"vector": v, "halfvec": h, "bit": b}


def check_tail() -> dict[str, float]:
    rng = random.Random(5)
    singles = [call_latency(rng) for _ in range(40_000)]
    t99 = pct(singles, 0.99)
    # the threshold is itself estimated, so measure how often a FRESH call exceeds it and use that rate in the formula
    q_hat = sum(call_latency(rng) > t99 for _ in range(100_000)) / 100_000
    assert 0.007 < q_hat < 0.013, q_hat
    results = {}
    for n in (1, 10, 50):
        trials = 6000
        slow = sum(max(call_latency(rng) for _ in range(n)) > t99 for _ in range(trials)) / trials
        results[n] = slow
        # tolerance ~3 sigma of the combined sampling error (trials and the estimated exceedance rate)
        assert abs(slow - p_any_slow(n, q_hat)) < 0.04, (n, slow, p_any_slow(n, q_hat))
    assert results[50] > 0.3 and results[1] < 0.03, results
    # hedging: second copy after the single-call p95; measure the tail and the extra load
    d = pct(singles, 0.95)
    hedged, extra = [], 0
    for _ in range(40_000):
        lat, sent = hedged_latency(rng, d)
        hedged.append(lat)
        extra += sent
    extra_load = extra / 40_000
    p99_plain, p99_hedged = pct(singles, 0.99), pct(hedged, 0.99)
    assert 0.03 < extra_load < 0.07, extra_load
    assert p99_hedged < 0.5 * p99_plain, (p99_plain, p99_hedged)
    # percentiles do not add: three sequential stages
    sums, stages = [], [[], [], []]
    for _ in range(30_000):
        xs = [call_latency(rng) for _ in range(3)]
        sums.append(sum(xs))
        for i, x in enumerate(xs):
            stages[i].append(x)
    sum_of_p95 = sum(pct(s, 0.95) for s in stages)
    p95_of_sum = pct(sums, 0.95)
    assert p95_of_sum < sum_of_p95, (p95_of_sum, sum_of_p95)
    # a latency budget built by adding per-stage p95 over-allocates; building it from the sum's percentile does not
    assert approx(littles_law(50, 2.0), 100.0)
    return {"fanout_slow_n1": results[1], "fanout_slow_n10": results[10], "fanout_slow_n50": results[50],
            "extra_load": extra_load, "p99_plain_ms": p99_plain, "p99_hedged_ms": p99_hedged,
            "p95_of_sum_ms": p95_of_sum, "sum_of_p95_ms": sum_of_p95}


def run_checks() -> dict[str, object]:
    out: dict[str, object] = {}
    out["cost"] = check_cost()
    out["storage"] = check_storage()
    out["tail"] = check_tail()
    return out


def main() -> None:
    r = run_checks()
    c, s, t = r["cost"], r["storage"], r["tail"]  # type: ignore[assignment]
    print(f"prefix-caching saving at 90% hit rate: {c['saving_small_prefix']:.1%} with an 800-token prefix, "  # type: ignore[index]
          f"{c['saving_big_prefix']:.1%} with a 6000-token prefix; hit probability at 0.1 req/min with a 5-min TTL: {c['hit_at_0.1_per_min']:.2f}")  # type: ignore[index]
    print("1M x 1536-dim raw vector bytes:", s)
    print(f"fan-out: P(at least one call beyond its own p99) = {t['fanout_slow_n1']:.3f} (n=1), {t['fanout_slow_n10']:.3f} (n=10), {t['fanout_slow_n50']:.3f} (n=50)")  # type: ignore[index]
    print(f"hedging after p95: extra load {t['extra_load']:.1%}, p99 {t['p99_plain_ms']:.0f} ms -> {t['p99_hedged_ms']:.0f} ms (simulated)")  # type: ignore[index]
    print(f"three sequential stages: p95 of the sum {t['p95_of_sum_ms']:.0f} ms < sum of stage p95s {t['sum_of_p95_ms']:.0f} ms")  # type: ignore[index]
    print("OK: all assertions hold (abstract prices, assumed latency distributions; no real system measured).")


MUTANT_NAMES = ["read-uses-write-mult", "break-even-wrong", "halfvec-as-float32", "bit-bytes-wrong", "fanout-linear", "hedge-immediately", "littles-law-wrong"]


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
