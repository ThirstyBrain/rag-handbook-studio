"""Chapter 2 exercise: similarity metrics on toy vectors (stdlib only).

Demonstrates, on made-up 4-d vectors:
  1. cosine similarity ignores magnitude; dot product and Euclidean distance do not
  2. for unit-length vectors, cosine, dot product and Euclidean distance
     produce the SAME ranking (||a-b||^2 = 2 - 2*cos(a,b))
  3. pgvector's <#> operator returns the NEGATIVE inner product

Run:  python ch02_similarity_demo.py
The vectors are illustrative; they are not real embeddings.
"""
from __future__ import annotations

import math


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def cosine(a: list[float], b: list[float]) -> float:
    return dot(a, b) / (norm(a) * norm(b))


def euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def unit(a: list[float]) -> list[float]:
    n = norm(a)
    return [x / n for x in a]


def rank(query: list[float], docs: dict[str, list[float]], metric: str) -> list[str]:
    if metric == "cosine":
        key = lambda name: -cosine(query, docs[name])  # noqa: E731
    elif metric == "dot":
        key = lambda name: -dot(query, docs[name])  # noqa: E731
    elif metric == "l2":
        key = lambda name: euclidean(query, docs[name])  # noqa: E731
    else:
        raise ValueError(metric)
    return sorted(docs, key=key)


def main() -> None:
    query = [1.0, 2.0, 0.5, 0.0]
    docs = {
        "A": [2.0, 4.0, 1.0, 0.0],      # same direction as query, 2x magnitude
        "B": [0.9, 2.1, 0.4, 0.1],      # close to query, similar magnitude
        "C": [0.0, 0.5, 3.0, 2.0],      # different direction
        "D": [10.0, 20.0, 5.0, 0.0],    # same direction, 10x magnitude
    }

    print("== Raw (non-normalized) vectors ==")
    for metric in ("cosine", "dot", "l2"):
        print(f"{metric:>6}: {rank(query, docs, metric)}")
    # Cosine ties A, B-ish, D on direction; dot rewards magnitude (D first); L2 punishes it.
    assert rank(query, docs, "dot")[0] == "D"
    assert rank(query, docs, "l2")[0] == "B"
    assert abs(cosine(query, docs["A"]) - cosine(query, docs["D"])) < 1e-12

    print("\n== Unit-normalized vectors ==")
    q_u = unit(query)
    d_u = {k: unit(v) for k, v in docs.items()}
    r_cos = rank(q_u, d_u, "cosine")
    r_dot = rank(q_u, d_u, "dot")
    r_l2 = rank(q_u, d_u, "l2")
    print(f"cosine: {r_cos}\n   dot: {r_dot}\n    l2: {r_l2}")
    assert r_cos == r_dot == r_l2 or {r_cos[2], r_cos[3]} == {r_dot[2], r_dot[3]}

    # Identity for unit vectors: ||a-b||^2 = 2 - 2 cos(a, b)
    for name, v in d_u.items():
        lhs = euclidean(q_u, v) ** 2
        rhs = 2 - 2 * cosine(q_u, v)
        assert abs(lhs - rhs) < 1e-12, name
    print("identity ||a-b||^2 == 2 - 2cos(a,b) holds for all unit vectors")

    print("\n== pgvector operator semantics (computed by hand here) ==")
    for name, v in d_u.items():
        ip = dot(q_u, v)
        print(f"{name}: <#> (negative inner product) = {-ip:+.4f}   cosine distance <=> = {1 - cosine(q_u, v):.4f}")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
