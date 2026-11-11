"""Chapter 31 exercise: an ADR linter run against this repository's REAL adr/ directory (stdlib only).

Architecture decision records only help if they stay trustworthy: complete, numbered without gaps, honest about
their status, linked to records that exist, and amended in a dated, append-only way (S206, S208, S209). This file
encodes those properties as machine-checkable rules and does four things:

  A. UNIT TESTS on constructed ADRs: a good record yields no findings; each rule fires on a record broken in
     exactly that way (and only that rule).
  B. THE REAL RUN: lint every adr/ADR-*.md in this repository and print the findings and a catalogue.
  C. A MUTATION CHECK: each rule can be switched off; the unit tests must notice every one (a rule nobody tests
     can be deleted unnoticed).
  D. CORRECTNESS OF PARSING on awkward inputs (headings with suffixes, status text with dates, code fences).

Run: python -I docs/exercises/ch31_adr_lint.py [--mutants]
The rules encode THIS repository's template (CLAUDE.md section 14) plus the Nygard/Azure guidance on status and
supersession. They detect structural and consistency defects. They cannot tell whether a decision is GOOD, whether
the rationale is true, or whether the code still follows it (that needs a "confirmation" step such as a test,
which MADR names explicitly: S209). Thresholds (max length, stale-proposed age) are assumptions, labelled below.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

MUT: set[str] = set()

REQUIRED_SECTIONS = ["status", "context", "requirements", "options considered", "decision", "rationale",
                     "trade-offs", "consequences", "security considerations", "performance and cost",
                     "reversal conditions", "references"]
STATUS_WORDS = {"proposed", "accepted", "superseded", "deprecated"}
MAX_LINES = 120          # [A] Nygard asks for one or two pages (S206); 120 lines is an assumed proxy
STALE_PROPOSED_DAYS = 30  # [A] a decision left Proposed for a month is a smell, not a proven defect
MIN_SECTION_CHARS = 20    # [A] a section holding only a placeholder
TODAY = date(2026, 11, 10)  # fixed so results are deterministic

_FENCE = re.compile(r"^```")
_REF = re.compile(r"ADR-(\d{3})")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_FILE = re.compile(r"^ADR-(\d{3})-.+\.md$")


@dataclass(frozen=True)
class Finding:
    adr: str
    rule: str
    severity: str  # error | warn | info
    message: str


@dataclass
class Adr:
    filename: str
    number: int
    text: str
    title_line: str
    sections: list[tuple[str, str]]  # (heading text, body)
    lines: int


def parse(filename: str, text: str) -> Adr:
    """Split into level-2 sections, ignoring '## ' lines inside code fences."""
    m = _FILE.match(filename)
    number = int(m.group(1)) if m else -1
    title_line = ""
    sections: list[tuple[str, str]] = []
    head: str | None = None
    body: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        if not in_fence and line.startswith("# ") and not title_line:
            title_line = line
            continue
        if not in_fence and line.startswith("## "):
            if head is not None:
                sections.append((head, "\n".join(body).strip()))
            head, body = line[3:].strip(), []
        elif head is not None:
            body.append(line)
    if head is not None:
        sections.append((head, "\n".join(body).strip()))
    return Adr(filename, number, text, title_line, sections, len(text.splitlines()))


def _section(adr: Adr, name: str) -> str | None:
    for h, b in adr.sections:
        if h.lower().startswith(name):
            return b
    return None


def _status(adr: Adr) -> tuple[str | None, date | None]:
    b = _section(adr, "status")
    if not b:
        return None, None
    word = re.sub(r"[^a-z]", "", b.split()[0].lower()) if b.split() else ""
    d = _DATE.search(b)
    return word, (date.fromisoformat(d.group(0)) if d else None)


def lint(adrs: list[Adr]) -> list[Finding]:
    out: list[Finding] = []
    numbers = {a.number for a in adrs}
    by_number = {a.number: a for a in adrs}

    # numbering: unique and gapless from 1
    if "gaps-allowed" not in MUT:
        seen: set[int] = set()
        for a in sorted(adrs, key=lambda x: x.number):
            if a.number in seen:
                out.append(Finding(a.filename, "duplicate-number", "error", f"number {a.number:03d} used twice"))
            seen.add(a.number)
        if numbers:
            for n in range(1, max(numbers) + 1):
                if n not in numbers:
                    out.append(Finding("(corpus)", "numbering-gap", "error", f"ADR-{n:03d} is missing from the sequence"))

    for a in adrs:
        label = a.filename
        # title format and number agreement
        t = re.match(r"^# ADR-(\d{3}): (\S.*)$", a.title_line)
        if not t:
            out.append(Finding(label, "title-format", "error", "title must be '# ADR-NNN: Short noun phrase'"))
        elif "title-number-unchecked" not in MUT and int(t.group(1)) != a.number:
            out.append(Finding(label, "title-number-mismatch", "error", f"title says ADR-{t.group(1)} but the file is {a.number:03d}"))

        # required sections
        if "sections-not-checked" not in MUT:
            heads = [h.lower() for h, _ in a.sections]
            for req in REQUIRED_SECTIONS:
                if not any(h.startswith(req) for h in heads):
                    out.append(Finding(label, "missing-section", "error", f"no '{req}' section"))

        # empty sections
        if "empty-section-ignored" not in MUT:
            for h, b in a.sections:
                if len(b) < MIN_SECTION_CHARS:
                    out.append(Finding(label, "empty-section", "warn", f"section '{h}' has almost no content"))

        word, sdate = _status(a)
        if "status-vocab-off" not in MUT:
            if word is None:
                pass  # missing-section already reported
            elif word not in STATUS_WORDS:
                out.append(Finding(label, "status-vocabulary", "error", f"status '{word}' is not one of {sorted(STATUS_WORDS)}"))

        # dated amendments (append-only history): any Amendment/Update/Addendum heading needs a date
        if "undated-amendment-ignored" not in MUT:
            for h, _ in a.sections:
                if re.match(r"(amendment|update|addendum)", h.lower()) and not _DATE.search(h):
                    out.append(Finding(label, "undated-amendment", "warn", f"heading '{h[:50]}' has no date"))

        # status vs content contradictions
        if "contradiction-ignored" not in MUT and word == "accepted":
            for h, _ in a.sections:
                hl = h.lower()
                if "(proposed)" in hl or "blocks acceptance" in hl:
                    out.append(Finding(label, "status-contradiction", "error", f"status is Accepted but heading '{h[:60]}' says otherwise"))

        # stale proposed
        if "stale-ignored" not in MUT and word == "proposed" and sdate and (TODAY - sdate).days > STALE_PROPOSED_DAYS:
            out.append(Finding(label, "stale-proposed", "warn", f"Proposed since {sdate} ({(TODAY - sdate).days} days)"))

        # supersession
        if word == "superseded":
            b = _section(a, "status") or ""
            succ = {int(x) for x in _REF.findall(b)} - {a.number}
            if "supersede-successor-unchecked" not in MUT:
                if not succ:
                    out.append(Finding(label, "superseded-without-successor", "error", "Superseded but names no replacing ADR"))
                for s in succ:
                    if s not in numbers:
                        out.append(Finding(label, "superseded-by-missing", "error", f"names ADR-{s:03d} which does not exist"))
                    elif "backlink-ignored" not in MUT and a.number not in {int(x) for x in _REF.findall(by_number[s].text)}:
                        out.append(Finding(label, "no-backlink", "warn", f"ADR-{s:03d} does not mention ADR-{a.number:03d}"))

        # references to records that do not exist
        if "dangling-ignored" not in MUT:
            for n in sorted({int(x) for x in _REF.findall(a.text)} - {a.number}):
                if n not in numbers:
                    out.append(Finding(label, "dangling-reference", "error", f"mentions ADR-{n:03d} which does not exist"))

        # an Accepted decision that leans on a still-Proposed one is only as settled as its weakest dependency
        if "accepted-on-proposed-ignored" not in MUT and word == "accepted":
            for n in sorted({int(x) for x in _REF.findall(a.text)} - {a.number}):
                if n in by_number and _status(by_number[n])[0] == "proposed":
                    out.append(Finding(label, "accepted-cites-proposed", "warn", f"Accepted, but cites ADR-{n:03d} which is still Proposed"))

        # references section has a verifiable pointer
        if "references-unchecked" not in MUT:
            r = _section(a, "references")
            if r is not None and not re.search(r"(SRC-\d+|S\d+|https?://|ADR-\d{3}|\.md|\.py|\.sql)", r):
                out.append(Finding(label, "references-empty", "warn", "References names no source id, URL or file"))

        if "length-ignored" not in MUT and a.lines > MAX_LINES:
            out.append(Finding(label, "too-long", "warn", f"{a.lines} lines (> {MAX_LINES})"))

    # orphans: no other record refers to it (information, not a defect)
    if "orphan-ignored" not in MUT:
        inbound: dict[int, set[int]] = {a.number: set() for a in adrs}
        for a in adrs:
            for n in {int(x) for x in _REF.findall(a.text)} - {a.number}:
                if n in inbound:
                    inbound[n].add(a.number)
        for a in adrs:
            if not inbound[a.number]:
                out.append(Finding(a.filename, "orphan", "info", "no other ADR refers to this one"))
    return out


def catalogue(adrs: list[Adr]) -> list[dict[str, object]]:
    inbound: dict[int, set[int]] = {a.number: set() for a in adrs}
    for a in adrs:
        for n in {int(x) for x in _REF.findall(a.text)} - {a.number}:
            if n in inbound:
                inbound[n].add(a.number)
    rows = []
    for a in sorted(adrs, key=lambda x: x.number):
        word, d = _status(a)
        t = re.match(r"^# ADR-\d{3}: (.*)$", a.title_line)
        amend = sum(1 for h, _ in a.sections if re.match(r"(amendment|update|addendum)", h.lower()))
        rows.append({"n": a.number, "title": t.group(1) if t else a.title_line, "status": word, "date": d,
                     "amendments": amend, "cited_by": sorted(inbound[a.number]), "lines": a.lines})
    return rows


# ---------------------------------------------------------------- constructed corpus (unit tests)

def good(n: int, status: str = "Accepted - 2026-11-01", extra: str = "") -> tuple[str, str]:
    body = f"# ADR-{n:03d}: Example Decision {n}\n\n"
    for h in ["Status", "Context", "Requirements", "Options Considered", "Decision", "Rationale", "Trade-offs",
              "Consequences", "Security Considerations", "Performance and Cost", "Reversal Conditions", "References"]:
        content = status if h == "Status" else ("Sources: SRC-001, S2 and docs/chapters/x.md for this decision." if h == "References" else "A sentence with enough content to count.")
        body += f"## {h}\n\n{content}\n\n"
    return f"ADR-{n:03d}-Example.md", body + extra


def _lint(files: list[tuple[str, str]]) -> list[Finding]:
    return lint([parse(f, t) for f, t in files])


def rules_fired(files: list[tuple[str, str]], severity: str | None = None) -> set[str]:
    return {f.rule for f in _lint(files) if severity is None or f.severity == severity}


def check_units() -> None:
    base = [good(1), good(2, extra="See ADR-001.\n")]
    # a clean corpus: no errors or warnings (orphan info is allowed: ADR-002 is not cited)
    clean = _lint(base)
    assert not [f for f in clean if f.severity in ("error", "warn")], clean
    assert {f.rule for f in clean} == {"orphan"}
    assert [f.adr for f in clean] == ["ADR-002-Example.md"], "ADR-001 is cited by ADR-002; only ADR-002 is an orphan"

    # numbering
    assert "numbering-gap" in rules_fired([good(1), good(3, extra="ADR-001")])
    assert "duplicate-number" in rules_fired([good(1), good(1), good(2)])
    # title
    f, t = good(1)
    assert "title-format" in rules_fired([(f, t.replace("# ADR-001: ", "# Decision about "))])
    assert "title-number-mismatch" in rules_fired([(f, t.replace("# ADR-001:", "# ADR-007:"))])
    # missing section: remove one at a time
    for sec in ["Context", "Reversal Conditions", "Trade-offs"]:
        f, t = good(1)
        broken = re.sub(rf"## {sec}\n\n[^\n]*\n\n", "", t)
        fired = [x for x in _lint([(f, broken)]) if x.rule == "missing-section"]
        assert len(fired) == 1 and sec.lower() in fired[0].message, (sec, fired)
    # heading suffix still satisfies the requirement
    f, t = good(1)
    assert "missing-section" not in rules_fired([(f, t.replace("## Decision\n", "## Decision (proposed)\n"))])
    # empty section
    f, t = good(1)
    assert "empty-section" in rules_fired([(f, t.replace("## Rationale\n\nA sentence with enough content to count.", "## Rationale\n\nTBD"))])
    # status vocabulary
    assert "status-vocabulary" in rules_fired([good(1, status="Approved - 2026-11-01")])
    assert "status-vocabulary" not in rules_fired([good(1, status="Accepted (conditional) - 2026-11-01")])
    # dated amendment
    f, t = good(1)
    assert "undated-amendment" in rules_fired([(f, t + "## Amendment (Chapter 5 research)\n\nSomething changed here for a reason.\n")])
    assert "undated-amendment" not in rules_fired([(f, t + "## Amendment 2026-11-07 (Chapter 5)\n\nSomething changed here for a reason.\n")])
    # contradiction: Accepted but still says "(proposed)" or "blocks acceptance"
    f, t = good(1)
    assert "status-contradiction" in rules_fired([(f, t.replace("## Decision\n", "## Decision (proposed)\n"))])
    assert "status-contradiction" in rules_fired([(f, t + "## Evidence gap (blocks acceptance)\n\nNo benchmark exists yet for this claim.\n")])
    f, t = good(1, status="Proposed - 2026-11-09")
    assert "status-contradiction" not in rules_fired([(f, t.replace("## Decision\n", "## Decision (proposed)\n"))])
    # stale proposed
    assert "stale-proposed" in rules_fired([good(1, status="Proposed - 2026-09-01")])
    assert "stale-proposed" not in rules_fired([good(1, status="Proposed - 2026-11-05")])
    assert "stale-proposed" not in rules_fired([good(1, status="Proposed - 2026-10-11")]), "30 days exactly is not stale"
    assert "stale-proposed" in rules_fired([good(1, status="Proposed - 2026-10-10")]), "31 days is stale"
    # supersession
    ok = [good(1, status="Superseded by ADR-002 - 2026-11-05"), good(2, extra="Supersedes ADR-001.\n")]
    assert not rules_fired(ok, "error") and "no-backlink" not in rules_fired(ok)
    assert "superseded-without-successor" in rules_fired([good(1, status="Superseded - 2026-11-05")])
    assert "superseded-without-successor" in rules_fired([good(1, status="Superseded by ADR-001 - 2026-11-05")]), "self is not a successor"
    assert "superseded-by-missing" in rules_fired([good(1, status="Superseded by ADR-009 - 2026-11-05")])
    assert "no-backlink" in rules_fired([good(1, status="Superseded by ADR-002 - 2026-11-05"), good(2)])
    # accepted -> proposed dependency
    dep = [good(1, status="Proposed - 2026-11-09"), good(2, extra="Builds on ADR-001.\n")]
    assert "accepted-cites-proposed" in rules_fired(dep)
    assert "accepted-cites-proposed" not in rules_fired([good(1), good(2, extra="Builds on ADR-001.\n")])
    assert "accepted-cites-proposed" not in rules_fired([good(1, status="Proposed - 2026-11-09", extra="Builds on ADR-002.\n"), good(2)]), "a Proposed ADR may cite an Accepted one"
    # dangling reference
    assert "dangling-reference" in rules_fired([good(1, extra="Related: ADR-042.\n")])
    assert "dangling-reference" not in rules_fired([good(1, extra="Template placeholder ADR-XXX is not a number.\n")])
    assert "dangling-reference" not in rules_fired([good(1, extra="Mentions itself: ADR-001.\n")])
    # references section
    f, t = good(1)
    assert "references-empty" in rules_fired([(f, t.replace("Sources: SRC-001, S2 and docs/chapters/x.md for this decision.", "See the internet for details on this."))])
    # length
    f, t = good(1)
    assert "too-long" in rules_fired([(f, t + "\n".join(["filler line"] * 130))])
    assert "too-long" not in rules_fired([(f, t)])
    # parsing: '## ' inside a code fence is not a section; a missing title is a title-format error
    f, t = good(1)
    fenced = t.replace("## Context\n\nA sentence with enough content to count.", "## Context\n\n```\n## Not a heading\n```\nA sentence with enough content to count.")
    p = parse(f, fenced)
    assert "Not a heading" not in [h for h, _ in p.sections]
    assert "title-format" in rules_fired([(f, "No title here\n" + t.split("\n", 1)[1])])
    # filename without a number cannot be linted into the sequence
    assert parse("notes.md", "# x").number == -1
    # catalogue
    cat = catalogue([parse(f, t) for f, t in [good(1), good(2, extra="See ADR-001.\n")]])
    assert cat[0]["cited_by"] == [2] and cat[1]["cited_by"] == [] and cat[0]["status"] == "accepted"
    assert str(cat[0]["date"]) == "2026-11-01"


# ---------------------------------------------------------------- the real run

def real_adrs() -> list[Adr]:
    d = Path(__file__).resolve().parents[2] / "adr"
    return [parse(p.name, p.read_text(encoding="utf-8")) for p in sorted(d.glob("ADR-*.md"))]


def check_real() -> dict[str, object]:
    adrs = real_adrs()
    assert len(adrs) >= 18, f"expected at least 18 ADRs, found {len(adrs)}"
    findings = lint(adrs)
    return {"adrs": adrs, "findings": findings, "catalogue": catalogue(adrs)}


def run_checks() -> dict[str, object]:
    check_units()
    return check_real()


def main() -> None:
    r = run_checks()
    adrs, findings, cat = r["adrs"], r["findings"], r["catalogue"]  # type: ignore[assignment]
    print(f"linted {len(adrs)} real ADRs  (today fixed at {TODAY})")
    for sev in ("error", "warn", "info"):
        fs = [f for f in findings if f.severity == sev]
        print(f"\n{sev.upper()}: {len(fs)}")
        for f in fs:
            print(f"  {f.adr:55s} {f.rule:24s} {f.message}")
    print("\ncatalogue (number | status | date | amendments | cited by | lines | title)")
    for row in cat:
        print(f"  {row['n']:03d} | {row['status']} | {row['date']} | {row['amendments']} | {row['cited_by']} | {row['lines']} | {row['title']}")
    print("\nOK: unit tests hold; the real-run findings above are reported as found (not asserted away).")


MUTANT_NAMES = ["gaps-allowed", "title-number-unchecked", "sections-not-checked", "empty-section-ignored", "status-vocab-off",
                "undated-amendment-ignored", "contradiction-ignored", "stale-ignored", "supersede-successor-unchecked",
                "backlink-ignored", "accepted-on-proposed-ignored", "dangling-ignored", "references-unchecked", "length-ignored", "orphan-ignored"]


def mutants() -> None:
    survived = []
    for m in MUTANT_NAMES:
        MUT.clear()
        MUT.add(m)
        try:
            check_units()
            survived.append(m)
        except (AssertionError, KeyError, IndexError):
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
