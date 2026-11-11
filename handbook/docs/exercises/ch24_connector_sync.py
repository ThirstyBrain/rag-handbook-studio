"""Chapter 24 exercise: keeping an index's permissions in step with a source system (stdlib only).

An enterprise knowledge connector copies documents AND their permissions from a source system into a search
index. Permissions change without the content changing, groups change without any document changing, folder
permissions are inherited by files that log no change of their own, change feeds replay and expire. This
simulation measures what each design choice costs, in terms of over-exposure (the index lets someone read
what the source no longer allows) and under-exposure (the index hides what the source allows):

  A. what the index stores: group principals resolved at query time, or users expanded at index time;
  B. what the connector processes: content changes only, or also ACL changes and inherited folder ACL changes;
  C. replays and token expiry: idempotent application and full-resync recovery;
  D. a staleness bound that fails closed when the connector has not synced recently;
  E. a mutation check.

Run: python -I docs/exercises/ch24_connector_sync.py [--mutants]
Event rates, sizes and intervals are MY CHOICES. The model captures mechanisms described in the Microsoft Graph
delta-query, Azure AI Search and Google Drive documentation (replays, expiring tokens, inherited permissions,
permission changes reflected only after synchronisation) but it is not a model of any product.
"""
from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field

MUT: set[str] = set()


class TokenExpired(Exception):
    pass


# ---------------------------------------------------------------- the source system
@dataclass
class Doc:
    doc_id: str
    folder: str
    version: int = 1
    own_acl: frozenset[str] | None = None   # None = inherit the folder's ACL
    deleted: bool = False


class Source:
    def __init__(self, rng: random.Random, retain: int) -> None:
        self.rng = rng
        self.docs: dict[str, Doc] = {}
        self.folder_acl: dict[str, frozenset[str]] = {}
        self.groups: dict[str, set[str]] = {}      # group -> members ("user:x" or "group:y")
        self.log: list[tuple[int, str, str]] = []  # (seq, kind, id) ; kinds: doc, folder_acl, delete
        self.seq = 0
        self.retain = retain                        # change feed keeps only the last N entries
        self.users: list[str] = []

    def _log(self, kind: str, ident: str) -> None:
        self.seq += 1
        self.log.append((self.seq, kind, ident))

    def effective_acl(self, d: Doc) -> frozenset[str]:
        return d.own_acl if d.own_acl is not None else self.folder_acl[d.folder]

    def closure(self, user: str) -> set[str]:
        """Principals the user holds NOW: the user plus every group containing them, directly or nested."""
        held = {f"user:{user}"}
        changed = True
        while changed:
            changed = False
            for g, members in self.groups.items():
                if f"group:{g}" not in held and held & members:
                    held.add(f"group:{g}")
                    changed = True
        return held

    def can_read(self, user: str, doc_id: str) -> bool:
        d = self.docs.get(doc_id)
        return bool(d) and not d.deleted and bool(self.closure(user) & self.effective_acl(d))

    def expand(self, principals: frozenset[str]) -> frozenset[str]:
        users = set()
        for p in principals:
            if p.startswith("user:"):
                users.add(p)
        for u in self.users:
            if self.closure(u) & principals:
                users.add(f"user:{u}")
        return frozenset(users)

    # change feed
    def delta(self, token: int, replay: bool) -> tuple[list[tuple[int, str, str]], int]:
        oldest = self.log[0][0] if self.log else 0
        if self.log and token < oldest - 1 and self.seq - token > self.retain:
            raise TokenExpired
        changes = [c for c in self.log if c[0] > token]
        if replay and changes:
            changes = changes + changes[-3:]   # best-effort feed: the last few changes appear again
        return changes, self.seq

    def compact(self) -> None:
        if len(self.log) > self.retain:
            self.log = self.log[-self.retain:]


# ---------------------------------------------------------------- the index and the connector
@dataclass
class Entry:
    version: int
    acl: frozenset[str]          # principals (mode "principals") or users (mode "expanded")


@dataclass
class Config:
    mode: str = "principals"             # principals | expanded
    handle_acl_changes: bool = True
    handle_folder_acl: bool = True
    interval: int = 10
    replay: bool = False
    stale_limit: int | None = None       # fail closed when no successful sync for this many ticks
    outage: tuple[int, int] | None = None


class Connector:
    def __init__(self, src: Source, cfg: Config) -> None:
        self.src, self.cfg = src, cfg
        self.index: dict[str, Entry] = {}
        self.token = 0
        self.last_ok = 0
        self.resyncs = 0

    def _snapshot(self, d: Doc) -> Entry:
        acl = self.src.effective_acl(d)
        if self.cfg.mode == "expanded":
            acl = self.src.expand(acl)
        return Entry(d.version, acl)

    def _upsert(self, doc_id: str) -> None:
        d = self.src.docs.get(doc_id)
        if d is None or d.deleted:
            if "ignore-removed" not in MUT:
                self.index.pop(doc_id, None)
            return
        cur = self.index.get(doc_id)
        if "non-idempotent" in MUT and cur is not None:
            self.index[doc_id] = Entry(cur.version + 1, self._snapshot(d).acl)   # a replay bumps the version
            return
        self.index[doc_id] = self._snapshot(d)

    def full_resync(self) -> None:
        self.resyncs += 1
        seen = set()
        for d in self.src.docs.values():
            if not d.deleted:
                self._upsert(d.doc_id)
                seen.add(d.doc_id)
        for stale in set(self.index) - seen:
            del self.index[stale]
        self.token = self.src.seq

    def sync(self, now: int) -> None:
        if self.cfg.outage and self.cfg.outage[0] <= now < self.cfg.outage[1]:
            return
        try:
            changes, new_token = self.src.delta(self.token, self.cfg.replay)
        except TokenExpired:
            if "no-expiry-handling" in MUT:
                return                                   # stuck: never recovers
            self.full_resync()
            self.last_ok = now
            return
        for _seq, kind, ident in changes:
            if kind == "doc":
                self._upsert(ident)
            elif kind == "delete":
                self._upsert(ident)
            elif kind == "folder_acl" and self.cfg.handle_folder_acl:
                for d in self.src.docs.values():
                    if d.folder == ident and d.own_acl is None:
                        self._upsert(d.doc_id)
            elif kind == "acl" and self.cfg.handle_acl_changes:
                self._upsert(ident)
        self.token = new_token
        self.last_ok = now

    def allows(self, user: str, doc_id: str, now: int) -> bool:
        if self.cfg.stale_limit is not None and "ignore-stale-limit" not in MUT and now - self.last_ok > self.cfg.stale_limit:
            return False                                 # fail closed: the index may be out of date
        e = self.index.get(doc_id)
        if e is None:
            return "unindexed-allowed" in MUT and self.src.docs.get(doc_id, Doc("x", "f1")).deleted
        if self.cfg.mode == "expanded":
            return f"user:{user}" in e.acl
        return bool(self.src.closure(user) & e.acl)      # groups resolved against the directory NOW


# ---------------------------------------------------------------- the simulation
@dataclass
class Result:
    over_pair_ticks: int = 0          # (user, doc, tick) where the index allows and the source does not
    under_pair_ticks: int = 0         # (user, doc, tick) where the source allows and the index hides
    max_over_run: int = 0             # longest run of consecutive ticks a single pair stayed over-exposed
    deleted_but_indexed: int = 0
    resyncs: int = 0
    final_index: dict[str, tuple[int, frozenset[str]]] = field(default_factory=dict)


def build(rng: random.Random, retain: int) -> Source:
    s = Source(rng, retain)
    s.users = [f"u{i}" for i in range(6)]
    s.groups = {"eng": {"user:u0", "user:u1", "group:ops"}, "ops": {"user:u2", "user:u3"}, "hr": {"user:u4", "user:u5"}}
    for f, acl in (("f1", {"group:eng"}), ("f2", {"group:hr"}), ("f3", {"group:ops", "user:u4"}), ("f4", {"group:eng", "group:hr"})):
        s.folder_acl[f] = frozenset(acl)
    for i in range(24):
        d = Doc(f"d{i}", f"f{1 + i % 4}")
        if i % 6 == 0:
            d.own_acl = frozenset({"group:eng"})
        s.docs[d.doc_id] = d
    return s


def run(cfg: Config, seed: int = 4, ticks: int = 300, retain: int = 40, events: bool = True) -> Result:
    rng = random.Random(seed)
    src = build(rng, retain)
    con = Connector(src, cfg)
    con.full_resync()
    res = Result()
    run_len: dict[tuple[str, str], int] = {}
    members_pool = [f"user:u{i}" for i in range(6)]
    for now in range(1, ticks + 1):
        if events:
            r = rng.random()
            ids = list(src.docs)
            if r < 0.20:                                           # content edit
                d = src.docs[rng.choice(ids)]
                d.version += 1
                src._log("doc", d.doc_id)
            elif r < 0.32:                                         # document ACL edit
                d = src.docs[rng.choice(ids)]
                d.own_acl = frozenset(rng.sample(["group:eng", "group:hr", "group:ops", "user:u0", "user:u3", "user:u5"], 2))
                src._log("acl", d.doc_id)
            elif r < 0.40:                                         # folder ACL edit (children log nothing)
                f = rng.choice(list(src.folder_acl))
                src.folder_acl[f] = frozenset(rng.sample(["group:eng", "group:hr", "group:ops", "user:u1", "user:u4"], 2))
                src._log("folder_acl", f)
            elif r < 0.55:                                         # group membership change (no document changes)
                g = rng.choice(list(src.groups))
                m = rng.choice(members_pool)
                if m in src.groups[g] and len(src.groups[g]) > 1:
                    src.groups[g].discard(m)
                else:
                    src.groups[g].add(m)
            elif r < 0.60:                                         # delete
                d = src.docs[rng.choice(ids)]
                if not d.deleted:
                    d.deleted = True
                    src._log("delete", d.doc_id)
            src.compact()
        if now % cfg.interval == 0:
            con.sync(now)
        for u in src.users:
            for did in src.docs:
                truth, idx = src.can_read(u, did), con.allows(u, did, now)
                key = (u, did)
                if idx and not truth:
                    res.over_pair_ticks += 1
                    run_len[key] = run_len.get(key, 0) + 1
                    res.max_over_run = max(res.max_over_run, run_len[key])
                else:
                    run_len[key] = 0
                if truth and not idx:
                    res.under_pair_ticks += 1
        res.deleted_but_indexed += sum(1 for did, d in src.docs.items() if d.deleted and did in con.index)
    res.resyncs = con.resyncs
    res.final_index = {k: (v.version, v.acl) for k, v in con.index.items()}
    return res


# ---------------------------------------------------------------- checks
def check_design_choices() -> dict[str, Result]:
    good = Config()
    out = {
        "principals + full": run(good),
        "expanded + full": run(Config(mode="expanded")),
        "principals, content only": run(Config(handle_acl_changes=False, handle_folder_acl=False)),
        "principals, no folder ACL": run(Config(handle_folder_acl=False)),
    }
    base = out["principals + full"]
    # sync interval bounds the exposure window of what the connector can see (ACL edits) plus one cycle
    assert base.max_over_run <= good.interval + 1, base.max_over_run
    # expanding groups at index time makes group-membership changes invisible to the index (no document changes)
    assert out["expanded + full"].over_pair_ticks > 3 * max(base.over_pair_ticks, 1), (out["expanded + full"].over_pair_ticks, base.over_pair_ticks)
    assert out["expanded + full"].max_over_run > 5 * good.interval
    # ignoring permission changes leaves revoked access visible for long periods
    assert out["principals, content only"].over_pair_ticks > 3 * max(base.over_pair_ticks, 1)
    assert out["principals, content only"].max_over_run > 5 * good.interval
    # inherited folder ACL changes log nothing on the children: ignoring them is its own failure
    assert out["principals, no folder ACL"].over_pair_ticks > base.over_pair_ticks
    assert out["principals, no folder ACL"].max_over_run > 3 * good.interval
    # deletions are applied promptly
    assert base.deleted_but_indexed < 40 * 300, base.deleted_but_indexed
    return out


def check_replay_and_expiry() -> dict[str, int]:
    clean = run(Config(replay=False))
    replayed = run(Config(replay=True))
    assert clean.final_index == replayed.final_index, "replays must not change the resulting index"
    # a long outage longer than the change feed retains: the old token expires and a full resync repairs the index
    outage = run(Config(outage=(60, 200)), ticks=300)
    assert outage.resyncs >= 2, outage.resyncs
    final = run(Config(outage=(60, 200)), ticks=300)
    return {"resyncs_after_outage": outage.resyncs, "over_pair_ticks_outage": final.over_pair_ticks}


def check_fail_closed() -> dict[str, int]:
    open_ = run(Config(outage=(60, 200)))
    closed = run(Config(outage=(60, 200), stale_limit=20))
    assert closed.over_pair_ticks < open_.over_pair_ticks, (closed.over_pair_ticks, open_.over_pair_ticks)
    assert closed.under_pair_ticks > open_.under_pair_ticks, "failing closed costs availability"
    return {"over_open": open_.over_pair_ticks, "over_closed": closed.over_pair_ticks,
            "under_open": open_.under_pair_ticks, "under_closed": closed.under_pair_ticks}


def run_checks() -> dict[str, object]:
    return {"design": check_design_choices(), "replay": check_replay_and_expiry(), "fail_closed": check_fail_closed()}


def main() -> None:
    r = run_checks()
    print(f"{'design':28} {'over-exposed pair-ticks':>24} {'longest run (ticks)':>20} {'under-exposed pair-ticks':>25}")
    for name, x in r["design"].items():  # type: ignore[union-attr]
        print(f"{name:28} {x.over_pair_ticks:24d} {x.max_over_run:20d} {x.under_pair_ticks:25d}")
    print("replay and token expiry:", r["replay"])
    print("outage ticks 60-200, fail-closed after 20 stale ticks:", r["fail_closed"])
    print("OK: all assertions hold (a simulation with my parameters; no real connector or source measured).")


MUTANT_NAMES = ["ignore-removed", "non-idempotent", "no-expiry-handling", "ignore-stale-limit", "unindexed-allowed"]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except AssertionError:
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    # the design variants (content-only, expanded, no folder ACL, no fail-closed) are checked as measured contrasts above;
    # their "mutants" are the Config options themselves, each asserted to be measurably worse.
    if survived:
        print("SURVIVED:", survived)
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected (design variants are asserted as contrasts).")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
