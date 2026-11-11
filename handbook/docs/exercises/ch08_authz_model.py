"""Chapter 8 exercise: authorization models for RAG retrieval (stdlib only).

Demonstrates and asserts
  1. RBAC vs ABAC decisions, deny-by-default, on explicit examples.
  2. POLICY-TO-FILTER EQUIVALENCE: an ABAC policy is compiled into a retrieval-time
     filter over precomputed document attributes; a randomized property test checks
     that the compiled filter and the policy evaluator agree on 20,000 generated
     (user, document) pairs. This is the pattern for keeping "who may read what"
     identical between the policy engine and the search query.
  3. REVOCATION WINDOW: if a document's ACL stores GROUP ids and the caller's groups
     are resolved at query time, removing a user from a group takes effect at once;
     if the ACL is expanded to USER ids at ingest, access persists until the next
     sync (the documented behaviour of metadata-sync designs).
  4. Fail closed: documents with missing or unparseable ACL metadata are not returned.
  5. Tenant is checked FIRST and independently of any attribute rule.

Not covered: real identity providers, token validation, Postgres RLS (needs a database;
see OPEN-ISSUES), or any real model.

Run:  python -I ch08_authz_model.py
"""
from __future__ import annotations

import random
from dataclasses import dataclass

# ------------------------------------------------------------------ model -------
CLASSIFICATIONS = ["public", "internal", "confidential", "restricted"]
LEVEL = {c: i for i, c in enumerate(CLASSIFICATIONS)}


@dataclass(frozen=True)
class User:
    tenant: str
    uid: str
    groups: frozenset[str]
    clearance: str
    department: str
    region: str


@dataclass(frozen=True)
class Doc:
    doc_id: str
    tenant: str
    classification: str
    owner_dept: str
    region: str
    acl_groups: frozenset[str] | None     # None = ACL missing/unparseable
    acl_users: frozenset[str] = frozenset()


# ------------------------------------------------------- ABAC policy evaluator ----
def abac_allows(u: User, d: Doc) -> bool:
    """Reference policy (the 'policy decision point').

    Rule set (deny by default):
      R0  tenant must match.
      R1  document must have a parseable ACL (fail closed).
      R2  user clearance >= document classification.
      R3  region-bound documents ('eu') only for users in region 'eu'.
      R4  public docs: any user in tenant (after R0..R3).
      R5  otherwise: user must be in an ACL group, OR be the owner department
          for internal-or-below documents.
    """
    if u.tenant != d.tenant:
        return False
    if d.acl_groups is None:
        return False
    if LEVEL[u.clearance] < LEVEL[d.classification]:
        return False
    if d.region == "eu" and u.region != "eu":
        return False
    if d.classification == "public":
        return True
    if u.groups & d.acl_groups:
        return True
    return d.owner_dept == u.department and LEVEL[d.classification] <= LEVEL["internal"]


# ---------------------------------- compiled filter (the 'policy enforcement point')
def compile_filter(u: User):
    """Compile the policy for ONE user into a predicate over stored document attributes only.

    This is what a search query's WHERE clause / filter expression would encode. It must
    never call back into the policy evaluator.
    """
    max_level = LEVEL[u.clearance]
    allowed_classes = {c for c in CLASSIFICATIONS if LEVEL[c] <= max_level}
    regions_ok = {"eu", "us", "apac"} if u.region == "eu" else {"us", "apac"}

    def pred(d: Doc) -> bool:
        return (
            d.tenant == u.tenant
            and d.acl_groups is not None
            and d.classification in allowed_classes
            and d.region in regions_ok
            and (
                d.classification == "public"
                or bool(u.groups & d.acl_groups)
                or (d.owner_dept == u.department and d.classification in ("public", "internal"))
            )
        )

    return pred


def retrieve(user: User, docs: list[Doc], k: int, use_filter: bool = True) -> list[Doc]:
    pred = compile_filter(user)
    pool = [d for d in docs if pred(d)] if use_filter else list(docs)
    return pool[:k]            # limit AFTER filtering


# ------------------------------------------------------------------ tests --------
def main() -> None:
    alice = User("acme", "alice", frozenset({"eng"}), "internal", "eng", "us")
    hr = User("acme", "hr1", frozenset({"hr-admins", "eng"}), "restricted", "hr", "eu")
    bob = User("globex", "bob", frozenset({"eng"}), "restricted", "eng", "us")

    comp = Doc("comp", "acme", "restricted", "hr", "us", frozenset({"hr-admins"}))
    wiki = Doc("wiki", "acme", "internal", "eng", "us", frozenset({"eng"}))
    pub = Doc("pub", "acme", "public", "mkt", "us", frozenset())
    eu_doc = Doc("eu", "acme", "internal", "hr", "eu", frozenset({"eng"}))
    broken = Doc("broken", "acme", "public", "eng", "us", None)
    other = Doc("other", "globex", "public", "eng", "us", frozenset())

    # 1) explicit decisions
    assert not abac_allows(alice, comp)                  # clearance + ACL
    assert abac_allows(alice, wiki) and abac_allows(alice, pub)
    assert not abac_allows(alice, eu_doc)                # region rule
    assert abac_allows(hr, eu_doc) and abac_allows(hr, comp)
    assert not abac_allows(alice, other) and not abac_allows(bob, wiki)   # tenant first
    assert not abac_allows(alice, broken)                # fail closed
    print("1. explicit ABAC decisions (deny-by-default, tenant first, fail closed): OK")

    # 2) policy <-> filter equivalence (randomized property test)
    rng = random.Random(2026)
    tenants, depts, regions, groups = ["acme", "globex"], ["eng", "hr", "mkt"], ["us", "eu", "apac"], ["eng", "hr-admins", "legal", "fin"]
    n_pairs = 0
    for _ in range(400):
        u = User(rng.choice(tenants), "u", frozenset(g for g in groups if rng.random() < 0.4),
                 rng.choice(CLASSIFICATIONS), rng.choice(depts), rng.choice(regions))
        pred = compile_filter(u)
        for _ in range(50):
            d = Doc("d", rng.choice(tenants), rng.choice(CLASSIFICATIONS), rng.choice(depts), rng.choice(regions),
                    None if rng.random() < 0.05 else frozenset(g for g in groups if rng.random() < 0.3))
            assert pred(d) == abac_allows(u, d), (u, d)
            n_pairs += 1
    print(f"2. compiled filter == policy evaluator on {n_pairs:,} random (user, doc) pairs: OK")

    # 3) limit-after-filter: an unauthorised higher-ranked doc must not consume a slot
    ranked = [other, comp, broken, wiki, pub]            # 'search order' before authorisation
    got = retrieve(alice, ranked, k=2)
    assert [d.doc_id for d in got] == ["wiki", "pub"], got
    assert [d.doc_id for d in retrieve(alice, ranked, k=2, use_filter=False)] == ["other", "comp"]   # what a post-filter design risks
    print("3. top-k applied after authorisation (a post-filter design would leak/starve): OK")

    # 4) revocation window: groups at query time vs users expanded at ingest
    team_docs = Doc("team", "acme", "internal", "legal", "us", frozenset({"proj-x"}), acl_users=frozenset({"carol"}))
    carol = User("acme", "carol", frozenset({"proj-x"}), "internal", "fin", "us")
    assert abac_allows(carol, team_docs)
    carol_removed = User("acme", "carol", frozenset(), "internal", "fin", "us")          # removed from proj-x at the IdP
    # (a) ACL lists GROUPS, caller groups come from the current token -> immediate effect
    assert not abac_allows(carol_removed, team_docs)
    # (b) ACL was EXPANDED to user ids at ingest: stale until re-sync
    def expanded_allows(u: User, d: Doc) -> bool:
        return u.tenant == d.tenant and u.uid in d.acl_users
    assert expanded_allows(carol_removed, team_docs), "stale user-expanded ACL still grants access"
    synced = Doc("team", "acme", "internal", "legal", "us", frozenset({"proj-x"}), acl_users=frozenset())   # after next sync
    assert not expanded_allows(carol_removed, synced)
    print("4. group-id ACLs revoke at once; user-expanded ACLs stay open until the next sync: OK")

    # 5) every document with a missing ACL is excluded for every user
    for u in (alice, hr, bob):
        assert not compile_filter(u)(broken)
    print("5. missing ACL metadata fails closed: OK")

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
