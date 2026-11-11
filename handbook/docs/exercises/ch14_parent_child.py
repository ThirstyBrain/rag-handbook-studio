"""Chapter 14 exercise: parent-child (small-to-big) retrieval mechanics (stdlib only).

Toy corpus, lexical retrieval over CHILD chunks, expansion to PARENT sections. Verifies:
  A. precision of small chunks vs completeness of parents (facts covered, context tokens)
  B. de-duplication of children that share a parent
  C. auto-merging (replace several sibling hits by their parent above a threshold)
  D. permission-safe expansion (a restricted sibling must not ride along with its parent)
  E. token-budget enforcement and reading order
No language model and no embeddings. Tokens are whitespace words (a proxy, not a tokenizer).
Run: python -I docs/exercises/ch14_parent_child.py [--mutants]
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _toy_ir import BM25  # noqa: E402


@dataclass(frozen=True)
class Chunk:
    cid: str
    section: str
    ordinal: int
    text: str
    acl: tuple[str, ...] = ("all",)


CHUNKS = [
    Chunk("t1", "S-term", 1, "Termination of contractor agreements is governed by this section."),
    Chunk("t2", "S-term", 2, "A contractor must give 30 days written notice to terminate the agreement."),
    Chunk("t3", "S-term", 3, "Notice must be sent to the engagement manager."),
    Chunk("t4", "S-term", 4, "The final payment is issued within 14 days after the termination date."),
    Chunk("t5", "S-term", 5, "Severance calculations for named individuals are kept in the confidential annex.", acl=("hr",)),
    Chunk("p1", "S-pay", 1, "Contractors are paid monthly in arrears."),
    Chunk("p2", "S-pay", 2, "Invoices must be submitted by the fifth working day."),
    Chunk("p3", "S-pay", 3, "Payment is made within 30 days of invoice approval."),
    Chunk("e1", "S-equip", 1, "Laptops are returned to IT on the last working day."),
    Chunk("e2", "S-equip", 2, "Access badges are deactivated when equipment is returned."),
]
QUERY = "how many days notice must a contractor give to terminate and when is the final payment made"
FACTS = {"t2", "t4"}                       # the two chunks that together answer the question
USER_GROUPS = ("all",)


def authorized(c: Chunk, groups) -> bool:
    return bool(set(c.acl) & set(groups))


def words(text: str) -> int:
    return len(text.split())


def child_hits(query: str, k: int, groups=USER_GROUPS, *, authz: bool = True) -> list[str]:
    pool = [c for c in CHUNKS if (authorized(c, groups) or not authz)]
    bm = BM25({c.cid: c.text for c in pool})
    return [d for d, _ in bm.search(query, k)]


BY_ID = {c.cid: c for c in CHUNKS}
# Rows come back from a store in arbitrary physical order; reading order must come from `ordinal`, never from storage order.
STORE = list(reversed(CHUNKS))


def window_expand(hit: str, budget_words: int, groups=USER_GROUPS) -> list[str]:
    """Sentence-window alternative to whole-parent expansion: the hit plus nearest authorized neighbours within budget."""
    sec = sorted((c for c in STORE if c.section == BY_ID[hit].section and authorized(c, groups)), key=lambda c: c.ordinal)
    idx = next(i for i, c in enumerate(sec) if c.cid == hit)
    lo = hi = idx
    used = words(sec[idx].text)
    while True:
        grew = False
        if lo - 1 >= 0 and used + words(sec[lo - 1].text) <= budget_words:
            lo -= 1
            used += words(sec[lo].text)
            grew = True
        if hi + 1 < len(sec) and used + words(sec[hi + 1].text) <= budget_words:
            hi += 1
            used += words(sec[hi].text)
            grew = True
        if not grew:
            return [c.cid for c in sec[lo:hi + 1]]


def expand(hits: list[str], groups=USER_GROUPS, *, budget_words: int | None = None, dedupe: bool = True,
           acl_filter: bool = True, ordered: bool = True) -> list[tuple[str, list[str]]]:
    """Expand child hits to their parent sections. Returns [(section, [chunk ids in reading order])]."""
    out: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    used = 0
    for h in hits:                                              # hits are in rank order
        sec = BY_ID[h].section
        if dedupe and sec in seen:
            continue
        seen.add(sec)
        members = [c for c in STORE if c.section == sec and (authorized(c, groups) or not acl_filter)]
        if ordered:
            members.sort(key=lambda c: c.ordinal)
        cost = sum(words(c.text) for c in members)
        if budget_words is not None and used + cost > budget_words:
            continue                                            # skip a parent that does not fit; later (smaller) ones may
        used += cost
        out.append((sec, [c.cid for c in members]))
    return out


def auto_merge(hits: list[str], threshold: float = 0.4, groups=USER_GROUPS) -> list[tuple[str, list[str]]]:
    """Replace the hits of a section by the whole section when >= threshold of its authorized chunks were hit."""
    by_sec: dict[str, list[str]] = {}
    for h in hits:
        by_sec.setdefault(BY_ID[h].section, []).append(h)
    out = []
    for sec, hs in by_sec.items():
        total = [c for c in CHUNKS if c.section == sec and authorized(c, groups)]
        if len(hs) / len(total) >= threshold:
            out.append((sec, [c.cid for c in sorted(total, key=lambda c: c.ordinal)]))
        else:
            out.append((sec, sorted(hs, key=lambda cid: BY_ID[cid].ordinal)))
    return out


def facts_covered(blocks: list[tuple[str, list[str]]]) -> set[str]:
    return {cid for _, cids in blocks for cid in cids} & FACTS


def tokens_in(blocks) -> int:
    return sum(words(BY_ID[cid].text) for _, cids in blocks for cid in cids)


def run_assertions(*, expand_fn=expand, merge_fn=auto_merge, hits_fn=child_hits) -> None:
    # A. precision vs completeness
    h1 = hits_fn(QUERY, 1)
    only_child = [(BY_ID[h1[0]].section, h1)]
    assert len(facts_covered(only_child)) == 1, "a single child hit carries only one of the two needed facts"
    parent = expand_fn(h1)
    assert facts_covered(parent) == FACTS, "expanding the hit to its parent section recovers both facts"
    assert tokens_in(parent) > 2 * tokens_in(only_child), "completeness costs context tokens"
    # B. dedupe
    h4 = hits_fn(QUERY, 4)
    secs = [s for s, _ in expand_fn(h4)]
    assert len(secs) == len(set(secs)), "two hits in one section must produce ONE parent block"
    # C. auto-merge threshold
    merged = merge_fn(h4, threshold=0.4)
    m = dict(merged)
    assert m["S-term"] == ["t1", "t2", "t3", "t4"], "enough sibling hits -> the whole (authorized) section"
    assert set(m["S-pay"]) <= {"p1", "p2", "p3"} and len(m["S-pay"]) < 3, "a section with few hits stays at chunk level"
    # D. permission-safe expansion
    ids = [cid for _, cids in expand_fn(h4) for cid in cids]
    assert "t5" not in ids, "restricted sibling must not ride along with its parent"
    assert "t5" not in hits_fn("severance named individuals confidential annex", 3), "restricted chunk must not even be retrievable"
    # E. budget and order
    budget = 40
    b = expand_fn(h4, budget_words=budget)
    assert tokens_in(b) <= budget, "budget must hold"
    # Observed limitation of 'skip a parent that does not fit': the BEST parent (S-term, 41 words) is dropped and a weaker one kept.
    assert [s for s, _ in b] == ["S-pay"] and facts_covered(b) == set(), "skip-if-too-big can discard the best evidence"
    # Sentence-window alternative degrades gracefully: it keeps the hit and as much neighbourhood as fits.
    w40, w45 = window_expand("t2", 40), window_expand("t2", 45)
    assert "t2" in w40 and sum(words(BY_ID[c].text) for c in w40) <= 40 and "t4" not in w40
    assert {"t2", "t4"} <= set(w45) and sum(words(BY_ID[c].text) for c in w45) <= 45
    assert "t5" not in window_expand("t4", 200), "window expansion also respects the ACL"
    ordered = expand_fn(h1)
    assert ordered[0][1] == sorted(ordered[0][1], key=lambda cid: BY_ID[cid].ordinal), "children must be in reading order"


def main() -> None:
    print("query:", QUERY)
    for k in (1, 2, 3, 4):
        h = child_hits(QUERY, k)
        cov = facts_covered([(BY_ID[x].section, [x]) for x in h])
        print(f"  child top-{k}: {h}  facts covered: {sorted(cov)}")
    h1 = child_hits(QUERY, 1)
    p = expand(h1)
    print(f"  top-1 expanded to parent: {p}  tokens(words) child={words(BY_ID[h1[0]].text)} parent={tokens_in(p)}")
    h4 = child_hits(QUERY, 4)
    print("  top-4 children:", h4)
    print("  expand (dedupe):", expand(h4))
    print("  auto-merge 0.4 :", auto_merge(h4, 0.4))
    print("  expand w/ budget 40 words:", expand(h4, budget_words=40))
    run_assertions()
    print("OK: all assertions hold (toy corpus, lexical retrieval, no model).")


def mutants() -> None:
    kills = {
        "expansion-ignores-acl": dict(expand_fn=lambda h, *a, **k: expand(h, acl_filter=False)),
        "no-dedupe": dict(expand_fn=lambda h, *a, **k: expand(h, dedupe=False, **k)),
        "budget-ignored": dict(expand_fn=lambda h, *a, budget_words=None, **k: expand(h)),
        "unordered-children": dict(expand_fn=lambda h, *a, **k: expand(h, ordered=False, **k)),
        "retrieval-before-authz": dict(hits_fn=lambda q, k, groups=USER_GROUPS: child_hits(q, k, groups, authz=False)),
    }
    survived = []
    for name, kw in kills.items():
        try:
            run_assertions(**kw)
            survived.append(name)
        except AssertionError:
            print(f"  mutant killed: {name}")
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(kills)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
