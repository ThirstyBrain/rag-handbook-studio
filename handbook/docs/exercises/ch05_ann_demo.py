"""Chapter 5 exercise: storage arithmetic, IVF recall-vs-probes, and the
post-filter shortfall (stdlib only, deterministic seed).

IMPORTANT LIMITS - read before quoting any number from this script
  * Data are synthetic i.i.d. Gaussian vectors. They have NO cluster structure,
    which is the hardest case for IVF. Real embeddings are clustered, so real
    recall-vs-probes curves differ. The point is the SHAPE of the trade-off
    (more probes -> higher recall, slower), not the values.
  * "Cost" is counted as distance computations, a hardware-independent proxy
    for latency. It is not a latency measurement.
  * Part C SIMULATES the documented behaviour of post-filtering ANN indexes
    (candidate list of fixed size, filter applied afterwards). It is not pgvector.

Run:  python -I ch05_ann_demo.py
"""
from __future__ import annotations

import math
import random

# ---------------------------------------------------------------- Part A ------
def raw_bytes(n_vectors: int, dims: int, bytes_per_elem: float, overhead: int = 0) -> float:
    return n_vectors * (dims * bytes_per_elem + overhead)


def part_a() -> None:
    print("== A. Raw vector storage arithmetic ==")
    n, d = 1_000_000, 128
    f32 = raw_bytes(n, d, 4)
    print(f"1M x 128d float32 raw vectors: {f32 / 1e6:.1f} MB (decimal MB)")
    # Milvus' docs list IVF_FLAT at ~515 MB for the same shape; raw vectors alone are ~512 MB,
    # so the doc figure is consistent with 'raw vectors + small overhead'.
    assert 505 <= f32 / 1e6 <= 520

    # pgvector docs: vector = 4*dims + 8 bytes, halfvec = 2*dims + 8 bytes
    d2 = 1536
    v = raw_bytes(10_000_000, d2, 4, overhead=8)
    h = raw_bytes(10_000_000, d2, 2, overhead=8)
    print(f"10M x 1536d  vector  (4d+8 B): {v / 1e9:.1f} GB")
    print(f"10M x 1536d  halfvec (2d+8 B): {h / 1e9:.1f} GB  ({h / v:.1%} of vector)")
    assert abs(h / v - 0.5) < 0.01

    # scalar/binary quantization fractions of float32 (element sizes only, excl. graph/overhead)
    for name, b in (("int8", 1), ("int4", 0.5), ("1-bit", 1 / 8)):
        print(f"{name:>5}: {b / 4:.1%} of float32 element storage  (saving {1 - b / 4:.1%})")
    assert abs((1 - 1 / 4) - 0.75) < 1e-9 and abs((1 - 0.5 / 4) - 0.875) < 1e-9 and abs((1 - (1 / 8) / 4) - 0.96875) < 1e-9


# ---------------------------------------------------------------- Part B ------
def l2sq(a: list[float], b: list[float]) -> float:
    return sum((x - y) * (x - y) for x, y in zip(a, b, strict=True))


def kmeans(data: list[list[float]], k: int, iters: int, rng: random.Random) -> list[list[float]]:
    cents = [list(c) for c in rng.sample(data, k)]
    d = len(data[0])
    for _ in range(iters):
        buckets: list[list[list[float]]] = [[] for _ in range(k)]
        for v in data:
            j = min(range(k), key=lambda c: l2sq(v, cents[c]))
            buckets[j].append(v)
        for j, b in enumerate(buckets):
            if b:
                cents[j] = [sum(x[i] for x in b) / len(b) for i in range(d)]
    return cents


def part_b() -> None:
    print("\n== B. IVF recall vs probes (synthetic Gaussian data; shape only) ==")
    rng = random.Random(7)
    n, d, lists, nq, topk = 3000, 16, 30, 30, 10
    data = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(n)]
    queries = [[rng.gauss(0, 1) for _ in range(d)] for _ in range(nq)]

    cents = kmeans(data, lists, iters=4, rng=rng)
    inv: list[list[int]] = [[] for _ in range(lists)]
    for i, v in enumerate(data):
        inv[min(range(lists), key=lambda c: l2sq(v, cents[c]))].append(i)

    exact = [sorted(range(n), key=lambda i: l2sq(q, data[i]))[:topk] for q in queries]

    results = []
    for probes in (1, 2, 4, 8, 16, 30):
        hits = 0
        cost = 0
        for q, truth in zip(queries, exact, strict=True):
            order = sorted(range(lists), key=lambda c: l2sq(q, cents[c]))[:probes]
            cand = [i for c in order for i in inv[c]]
            cost += lists + len(cand)  # centroid comparisons + scanned vectors
            top = sorted(cand, key=lambda i: l2sq(q, data[i]))[:topk]
            hits += len(set(top) & set(truth))
        recall = hits / (nq * topk)
        avg_cost = cost / nq
        results.append((probes, recall, avg_cost))
        print(f"probes={probes:>2}  recall@{topk}={recall:.3f}  avg distance computations/query={avg_cost:,.0f}  (exact scan = {n:,})")

    recalls = [r for _, r, _ in results]
    costs = [c for _, _, c in results]
    assert all(b >= a - 1e-12 for a, b in zip(recalls, recalls[1:], strict=False)), "recall should not fall as probes rise"
    assert costs == sorted(costs), "work should rise with probes"
    assert abs(recalls[-1] - 1.0) < 1e-12, "probing every list must equal exact search"
    assert recalls[0] < recalls[-1], "low probes should lose recall on unstructured data"


# ---------------------------------------------------------------- Part C ------
def part_c() -> None:
    print("\n== C. Post-filter shortfall (simulation of documented behaviour) ==")
    rng = random.Random(11)
    n, ef, k, match_rate, trials = 20_000, 40, 10, 0.10, 400
    matches = [rng.random() < match_rate for _ in range(n)]  # e.g. 'tenant = acme' on 10% of rows

    # Candidate order = a random permutation (stands in for 'ANN returns nearest first';
    # the filter attribute is independent of similarity, which is the typical tenant case).
    def run(iterative: bool, max_scan: int = 20_000) -> float:
        total = 0
        for _ in range(trials):
            order = rng.sample(range(n), n)
            if not iterative:
                cand = order[:ef]                       # fixed candidate list, filter afterwards
                got = sum(matches[i] for i in cand)
            else:
                got = 0
                for scanned, i in enumerate(order, 1):  # keep scanning until k matches or limit
                    got += matches[i]
                    if got >= k or scanned >= max_scan:
                        break
            total += min(got, k)
        return total / trials

    plain = run(False)
    iter_ = run(True)
    print(f"filter matches {match_rate:.0%} of rows, ef_search={ef}, k={k}")
    print(f"post-filter, fixed candidates : avg results returned = {plain:.2f} of {k}  (documented example: ~{ef * match_rate:.0f})")
    print(f"iterative scan until k matched : avg results returned = {iter_:.2f} of {k}")
    assert 3.0 <= plain <= 5.0, plain            # expectation = ef * rate = 4
    assert iter_ >= 9.9, iter_                    # iterative continues until k found
    assert math.isclose(ef * match_rate, 4.0)


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    print("\nAll assertions passed.")
