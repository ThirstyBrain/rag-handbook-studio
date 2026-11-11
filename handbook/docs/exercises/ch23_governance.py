"""Chapter 23 exercise: governance as code (stdlib only).

Governance fails when it lives only in documents. This file makes four governance artefacts executable:

  A. an AI-system register entry and a validator that applies policy rules (owner, pinned models, data classes,
     provider locality, DPIA status, retention, human oversight, evidence, review date);
  B. a coverage check of the 12 risks named in NIST AI 600-1 (Generative AI Profile) against the controls of a
     system, so that no risk is silently unmapped: each is implemented/partial (evidence file must exist),
     planned (names the component) or explicitly accepted (rationale, owner, review date);
  C. an erasure-propagation simulation: a deletion request must reach every store that holds a copy, or the
     residual exposure window must be stated;
  D. a hash-chained, content-free audit log whose verification detects edits, deletions, insertions, reordering,
     and which refuses to record prompts or document text;
  E. a mutation check.

Run: python -I docs/exercises/ch23_governance.py [--mutants]
The policy thresholds, the register fields and the control mapping are ILLUSTRATIVE and are my choices for the
reference system. Nothing here is legal advice or a statement of what any law requires; the regulatory material
is discussed in Chapter 23 with its sources and limits.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MUT: set[str] = set()
ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- A. register and policy validator
DATA_CLASSES = {"public", "internal", "confidential", "restricted", "personal"}
RISK_TIERS = {"minimal", "limited", "high", "needs-legal-review"}
MAX_RETENTION_DAYS = 365


@dataclass(frozen=True)
class ModelRef:
    provider: str
    model_id: str
    version: str          # a pinned identifier, never "latest"
    locality: str         # local | external


@dataclass(frozen=True)
class AISystem:
    name: str
    owner: str
    purpose: str
    data_classes: frozenset[str]
    models: tuple[ModelRef, ...]
    risk_tier: str
    dpia_status: str                   # done | not-required-with-rationale | missing | n/a
    human_oversight: str               # "" when none
    evaluation_evidence: str           # id of the latest evaluation report, "" when none
    retention_days: int
    content_capture: str               # off | on
    content_capture_approval: str      # ticket id when capture is on
    review_due: date


def validate_system(s: AISystem, today: date) -> list[str]:
    f: list[str] = []
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s.owner):
        f.append("owner must be a named contact address")
    if not s.purpose.strip():
        f.append("purpose is required")
    if not s.data_classes <= DATA_CLASSES or not s.data_classes:
        f.append("data classes must be declared from the approved list")
    if not s.models:
        f.append("at least one model must be registered")
    for m in s.models:
        if m.version.strip().lower() in {"", "latest", "default"} and "allow-unpinned-models" not in MUT:
            f.append(f"model {m.model_id} must be pinned to a version")
        if m.locality == "external" and "restricted" in s.data_classes and "ignore-locality" not in MUT:
            f.append(f"restricted data must not reach external provider {m.provider}")
    if s.risk_tier not in RISK_TIERS:
        f.append("risk tier must be one of the defined tiers")
    if "personal" in s.data_classes and s.dpia_status not in {"done", "not-required-with-rationale"} and "skip-dpia-rule" not in MUT:
        f.append("personal data requires a completed DPIA or a recorded rationale")
    if s.risk_tier in {"high", "needs-legal-review"} and not s.human_oversight and "skip-oversight-rule" not in MUT:
        f.append("this risk tier requires a described human oversight arrangement")
    if s.risk_tier != "minimal" and not s.evaluation_evidence:
        f.append("an evaluation report reference is required above the minimal tier")
    if not 0 < s.retention_days <= MAX_RETENTION_DAYS:
        f.append(f"retention must be between 1 and {MAX_RETENTION_DAYS} days")
    if s.content_capture == "on" and not s.content_capture_approval and "capture-without-approval" not in MUT:
        f.append("content capture is on without an approval reference")
    if s.review_due < today and "ignore-review-date" not in MUT:
        f.append("review is overdue")
    return f


def triage(sensitive_domain: bool, public_facing: bool, personal_data: bool) -> str:
    """A WORKFLOW GATE, not a legal classification: anything that touches a sensitive domain goes to legal review
    before launch; public-facing systems get a transparency review."""
    if sensitive_domain:
        return "needs-legal-review"
    if public_facing:
        return "limited"
    return "minimal" if not personal_data else "limited"


# ---------------------------------------------------------------- B. coverage of the 12 NIST AI 600-1 risks
NIST_GAI_RISKS = (
    "CBRN Information or Capabilities", "Confabulation", "Dangerous, Violent, or Hateful Content", "Data Privacy",
    "Environmental Impacts", "Harmful Bias or Homogenization", "Human-AI Configuration", "Information Integrity",
    "Information Security", "Intellectual Property", "Obscene, Degrading, and/or Abusive Content",
    "Value Chain and Component Integration",
)


@dataclass(frozen=True)
class RiskMapping:
    risk: str
    status: str                          # implemented | partial | planned | accepted
    controls: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()       # repository paths that must exist for implemented/partial
    component: str = ""                  # for planned
    rationale: str = ""                  # for accepted
    owner: str = ""
    review_due: date | None = None


MAPPING = [
    RiskMapping("CBRN Information or Capabilities", "accepted", rationale="internal knowledge assistant; provider-side safeguards; revisit if public-facing", owner="security-lead@example.com", review_due=date(2027, 5, 1)),
    RiskMapping("Confabulation", "partial", ("citation validation (planned)", "faithfulness evaluation", "abstention"), ("docs/exercises/ch18_evaluation.py",), component="12"),
    RiskMapping("Dangerous, Violent, or Hateful Content", "planned", ("provider safety filters", "output policy"), component="11"),
    RiskMapping("Data Privacy", "partial", ("tenant isolation (RLS) [built]", "sensitivity policy [built]", "erasure propagation [partly built]", "PII redaction [exercise only]"), ("reference-implementation/tests/integration/test_schema_security.py", "docs/exercises/ch22_security_controls.py")),
    RiskMapping("Environmental Impacts", "accepted", rationale="tracked indirectly through token usage; no separate measurement", owner="platform-lead@example.com", review_due=date(2027, 5, 1)),
    RiskMapping("Harmful Bias or Homogenization", "partial", ("evaluation slices by language and segment",), ("docs/exercises/ch18_evaluation.py",), component="17"),
    RiskMapping("Human-AI Configuration", "planned", ("citations", "AI disclosure in the UI", "feedback"), component="15"),
    RiskMapping("Information Integrity", "partial", ("provenance per chunk", "versioned sources"), ("adr/ADR-017-Chunk-Embedding-During-Ingestion.md",), component="12"),
    RiskMapping("Information Security", "partial", ("sandboxed parsing [built]", "narrow roles [built]", "egress control [exercise only]", "evidence framing [exercise only]", "access re-check [exercise only]"), ("docs/exercises/ch22_security_controls.py", "reference-implementation/tests/unit/test_extraction_sandbox.py")),
    RiskMapping("Intellectual Property", "accepted", rationale="licence metadata not captured at ingestion; internal documents only", owner="legal-contact@example.com", review_due=date(2027, 2, 1)),
    RiskMapping("Obscene, Degrading, and/or Abusive Content", "accepted", rationale="enterprise corpus; relies on provider filters", owner="security-lead@example.com", review_due=date(2027, 5, 1)),
    RiskMapping("Value Chain and Component Integration", "implemented", ("model and provider register", "pinned versions", "dependency inventory"), ("reference-implementation/DEPENDENCIES.md", "adr/ADR-012-LLM-Gateway.md")),
]


def coverage_problems(mapping: list[RiskMapping], today: date) -> list[str]:
    p: list[str] = []
    by_risk = {m.risk: m for m in mapping}
    for r in NIST_GAI_RISKS:
        m = by_risk.get(r)
        if m is None:
            if "unmapped-ok" not in MUT:
                p.append(f"{r}: not mapped")
            continue
        if m.status in {"implemented", "partial"}:
            if not m.controls:
                p.append(f"{r}: no controls named")
            for ev in m.evidence:
                if not (ROOT / ev).exists() and "skip-evidence-check" not in MUT:
                    p.append(f"{r}: evidence file missing: {ev}")
            if not m.evidence and "no-evidence-ok" not in MUT:
                p.append(f"{r}: {m.status} requires evidence")
        elif m.status == "planned":
            if not m.component:
                p.append(f"{r}: planned without a component")
        elif m.status == "accepted":
            if not (m.rationale and m.owner and m.review_due):
                p.append(f"{r}: acceptance needs rationale, owner and review date")
            elif m.review_due < today and "ignore-acceptance-expiry" not in MUT:
                p.append(f"{r}: risk acceptance has expired")
        else:
            p.append(f"{r}: unknown status {m.status}")
    return p


# ---------------------------------------------------------------- C. erasure propagation
@dataclass
class Store:
    name: str
    holds_personal_data: bool
    deletion: str                         # immediate | cascade | ttl:<days> | none
    items: set[str] = field(default_factory=set)


def erase(doc_id: str, stores: list[Store]) -> dict[str, object]:
    """Apply a deletion request. immediate and cascade stores lose the item now; ttl stores keep it until the
    retention period ends (reported as residual exposure); a store with no deletion path is a policy failure."""
    residual: dict[str, int] = {}
    failures: list[str] = []
    for s in stores:
        if doc_id not in s.items:
            continue
        if s.deletion == "immediate" or (s.deletion == "cascade" and "skip-cascade" not in MUT):
            s.items.discard(doc_id)
        elif s.deletion.startswith("ttl:"):
            if "ignore-ttl" not in MUT:
                residual[s.name] = int(s.deletion.split(":", 1)[1])
            else:
                s.items.discard(doc_id)
        else:
            failures.append(f"{s.name}: no deletion path")
    return {"residual_days": residual, "failures": failures, "max_residual_days": max(residual.values(), default=0)}


# ---------------------------------------------------------------- D. hash-chained, content-free audit log
FORBIDDEN_KEYS = {"prompt", "question", "answer", "content", "chunk_text", "document_text", "query_text"}
GENESIS = "0" * 64


class AuditLog:
    def __init__(self) -> None:
        self.entries: list[dict[str, object]] = []

    @staticmethod
    def _digest(prev: str, body: dict[str, object]) -> str:
        payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((("" if "hash-without-prev" in MUT else prev) + payload).encode()).hexdigest()

    def append(self, event: dict[str, object]) -> None:
        if FORBIDDEN_KEYS & {k.lower() for k in event} and "allow-content" not in MUT:
            raise ValueError("audit events carry identifiers, never content")
        prev = self.entries[-1]["hash"] if self.entries else GENESIS
        self.entries.append({"seq": len(self.entries), "event": event, "prev": prev, "hash": self._digest(str(prev), {"seq": len(self.entries), "event": event})})

    def head(self) -> str:
        return str(self.entries[-1]["hash"]) if self.entries else GENESIS

    def verify(self, anchor: str | None = None) -> bool:
        """Check the chain. `anchor` is a head hash published somewhere the log's writer cannot modify; without it
        an attacker who can rewrite the whole log can rebuild a valid chain."""
        if anchor is not None and "ignore-anchor" not in MUT and self.head() != anchor:
            return False
        prev = GENESIS
        for i, e in enumerate(self.entries):
            if e["seq"] != i:
                return False
            if e["prev"] != prev and "ignore-prev-link" not in MUT:
                return False
            if e["hash"] != self._digest(str(e["prev"] if "ignore-prev-link" in MUT else prev), {"seq": e["seq"], "event": e["event"]}):
                return False
            prev = str(e["hash"])
        return True


# ---------------------------------------------------------------- checks
TODAY = date(2026, 11, 9)


def good_system() -> AISystem:
    return AISystem("kb-assistant", "owner@example.com", "answer staff questions from internal policies",
                    frozenset({"internal", "personal"}), (ModelRef("local", "embed-model", "2026-05", "local"),), "limited",
                    "done", "reviewer approves escalations", "EVAL-2026-11", 90, "off", "", date(2027, 3, 1))


def replace(s: AISystem, **kw: object) -> AISystem:
    d = {**s.__dict__, **kw}
    return AISystem(**d)  # type: ignore[arg-type]


def check_register() -> None:
    assert validate_system(good_system(), TODAY) == []
    s = good_system()
    cases = [
        (replace(s, owner="team"), "owner"),
        (replace(s, models=(ModelRef("p", "m", "latest", "local"),)), "pinned"),
        (replace(s, data_classes=frozenset({"restricted"}), models=(ModelRef("ext", "m", "1", "external"),)), "external provider"),
        (replace(s, dpia_status="missing"), "DPIA"),
        (replace(s, risk_tier="high", human_oversight=""), "oversight"),
        (replace(s, evaluation_evidence=""), "evaluation"),
        (replace(s, retention_days=4000), "retention"),
        (replace(s, content_capture="on"), "capture"),
        (replace(s, review_due=date(2026, 1, 1)), "overdue"),
    ]
    for system, needle in cases:
        found = validate_system(system, TODAY)
        assert any(needle in x for x in found), (needle, found)
    assert triage(True, False, False) == "needs-legal-review" and triage(False, True, False) == "limited"
    assert triage(False, False, False) == "minimal" and triage(False, False, True) == "limited"


def check_coverage() -> None:
    assert coverage_problems(MAPPING, TODAY) == [], coverage_problems(MAPPING, TODAY)
    assert len(NIST_GAI_RISKS) == 12
    dropped = [m for m in MAPPING if m.risk != "Data Privacy"]
    assert any("not mapped" in x for x in coverage_problems(dropped, TODAY))
    ghost = [RiskMapping("Data Privacy", "implemented", ("x",), ("does/not/exist.md",)) if m.risk == "Data Privacy" else m for m in MAPPING]
    assert any("evidence file missing" in x for x in coverage_problems(ghost, TODAY))
    bare = [RiskMapping("Data Privacy", "implemented", ("x",)) if m.risk == "Data Privacy" else m for m in MAPPING]
    assert any("requires evidence" in x for x in coverage_problems(bare, TODAY))
    unowned = [RiskMapping("Environmental Impacts", "accepted", rationale="r") if m.risk == "Environmental Impacts" else m for m in MAPPING]
    assert any("acceptance needs" in x for x in coverage_problems(unowned, TODAY))
    expired = [RiskMapping("Environmental Impacts", "accepted", rationale="r", owner="o@example.com", review_due=date(2026, 1, 1)) if m.risk == "Environmental Impacts" else m for m in MAPPING]
    assert any("expired" in x for x in coverage_problems(expired, TODAY))


def check_erasure() -> dict[str, object]:
    def stores() -> list[Store]:
        d = "doc-1"
        return [Store("raw objects", True, "immediate", {d}), Store("chunks", True, "cascade", {d}), Store("vectors", True, "cascade", {d}),
                Store("full-text index", True, "cascade", {d}), Store("answer cache", True, "immediate", {d}),
                Store("golden set", True, "immediate", {d}), Store("backups", True, "ttl:35", {d}), Store("telemetry", False, "ttl:30", set())]
    ss = stores()
    out = erase("doc-1", ss)
    live = [s.name for s in ss if "doc-1" in s.items]
    assert live == ["backups"], live
    assert out["residual_days"] == {"backups": 35} and out["max_residual_days"] == 35 and out["failures"] == []
    orphan = stores() + [Store("analytics export", True, "none", {"doc-1"})]
    assert erase("doc-1", orphan)["failures"] == ["analytics export: no deletion path"]
    return {"max_residual_days": out["max_residual_days"]}


def check_audit() -> None:
    log = AuditLog()
    for i in range(5):
        log.append({"actor": f"user-{i}", "action": "retrieve", "tenant": "t1", "chunk_ids": [f"c{i}"]})
    assert log.verify() and len(log.entries) == 5
    for attack in ("edit", "delete", "insert", "reorder"):
        forged = AuditLog()
        forged.entries = [dict(e) for e in log.entries]
        if attack == "edit":
            forged.entries[2]["event"] = {"actor": "user-2", "action": "export", "tenant": "t1", "chunk_ids": ["c2"]}
        elif attack == "delete":
            del forged.entries[2]
        elif attack == "insert":
            forged.entries.insert(2, {"seq": 2, "event": {"actor": "x"}, "prev": forged.entries[1]["hash"], "hash": "f" * 64})
        else:
            forged.entries[1], forged.entries[2] = forged.entries[2], forged.entries[1]
        assert not forged.verify(), attack
    # rewriting an entry AND recomputing its own hash is still detected because the next entry's prev link breaks
    forged = AuditLog()
    forged.entries = [dict(e) for e in log.entries]
    forged.entries[1]["event"] = {"actor": "user-1", "action": "export"}
    forged.entries[1]["hash"] = AuditLog._digest(str(forged.entries[1]["prev"]), {"seq": 1, "event": forged.entries[1]["event"]})
    assert not forged.verify(), "a re-hashed edit breaks the chain at the next entry"
    # a smarter forger also patches the next entry's link: detected only because each hash covers the previous hash
    forged = AuditLog()
    forged.entries = [dict(e) for e in log.entries]
    forged.entries[1]["event"] = {"actor": "user-1", "action": "export"}
    forged.entries[1]["hash"] = AuditLog._digest(str(forged.entries[1]["prev"]), {"seq": 1, "event": forged.entries[1]["event"]})
    forged.entries[2]["prev"] = forged.entries[1]["hash"]
    assert not forged.verify(), "patching the next link is not enough: the next hash covers the previous hash"
    # the limit of a hash chain: someone who can rewrite EVERY later entry rebuilds a valid chain...
    anchor = log.head()  # ...so the head hash is published somewhere the writer cannot modify
    rebuilt = AuditLog()
    for e in log.entries:
        ev = {"actor": "user-1", "action": "export"} if e["seq"] == 1 else e["event"]
        rebuilt.append(ev)  # type: ignore[arg-type]
    assert rebuilt.verify(), "an unanchored chain can be rebuilt end to end"
    assert not rebuilt.verify(anchor=anchor), "an anchored head hash exposes the rebuild"
    assert log.verify(anchor=anchor)
    for key in ("prompt", "Question", "chunk_text"):
        try:
            AuditLog().append({"actor": "u", key: "secret text"})
            raise AssertionError(f"content key {key} accepted")
        except ValueError:
            pass


def run_checks() -> dict[str, object]:
    check_register()
    check_coverage()
    out = check_erasure()
    check_audit()
    return out


def main() -> None:
    r = run_checks()
    print("register rules: 9 violations detected; coverage of 12 NIST AI 600-1 risks: 0 problems;",
          f"erasure: personal data gone from every store except backups (up to {r['max_residual_days']} days); audit chain: edit/delete/insert/reorder/re-hash detected")
    print("OK: all assertions hold (illustrative policy and mapping; not legal advice).")


MUTANT_NAMES = ["allow-unpinned-models", "ignore-locality", "skip-dpia-rule", "skip-oversight-rule", "capture-without-approval",
                "ignore-review-date", "unmapped-ok", "skip-evidence-check", "no-evidence-ok", "ignore-acceptance-expiry",
                "skip-cascade", "ignore-ttl", "hash-without-prev", "ignore-prev-link", "allow-content", "ignore-anchor"]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            run_checks()
            survived.append(m)
        except (AssertionError, ValueError):
            print(f"  mutant killed: {m}")
        finally:
            MUT.clear()
    if survived:
        print("SURVIVED:", survived)
    assert not survived, f"mutants survived: {survived}"
    print(f"All {len(MUTANT_NAMES)} injected defects were detected.")


if __name__ == "__main__":
    main()
    if "--mutants" in sys.argv:
        print("\n== mutation check ==")
        mutants()
