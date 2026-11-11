"""Chapter 32/33 exercise: a structural lint for the scenario guide and the question bank (stdlib only).

An interview bank rots the way an ADR log does: duplicated questions, answers with no evidence tag, chapter pointers
that no longer exist, citations to sources nobody registered. This file encodes those properties as checks and does:

  A. UNIT TESTS on constructed inputs: a good document yields no findings; each rule fires on a document broken in
     exactly that way.
  B. THE REAL RUN: lint docs/chapters/32-*.md and docs/chapters/33-*.md of this repository.
  C. A MUTATION CHECK: each rule can be switched off; the unit tests must notice every one.

Run: python -I docs/exercises/ch33_bank_lint.py [--mutants]

What it can establish: structure, counts, uniqueness, pointer and source-id existence. What it cannot establish:
that an answer is TRUE, that a cited source supports the sentence, or that the question is a good one. Thresholds
(minimum 100 questions, 15 to 25 scenarios, at least 3 questions per chapter) come from CLAUDE.md 17.5 and the
Master TOC; the per-chapter minimum and the 60-character answer minimum are my own choices (assumptions).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

MUT: set[str] = set()  # rule ids switched off by the mutation check

ROOT = Path(__file__).resolve().parent.parent.parent
MAX_CHAPTER = 31
MIN_QUESTIONS = 100
MIN_PER_CHAPTER = 3
MIN_ANSWER_CHARS = 60
SCENARIO_RANGE = (15, 25)
DIFFICULTIES = ("foundational", "intermediate", "advanced")
SCENARIO_FIELDS = ("Prompt", "Clarify first", "Model architecture", "Trade-offs", "Failure modes", "Probes",
                   "Scoring focus", "Draws on")

Q_RE = re.compile(r"^\*\*Q(\d{3}) \[Ch (\d+) · (\w+)\]\*\* (.+)$")
A_RE = re.compile(r"^\*\*A\.\*\* (.+)$")
TAG_RE = re.compile(r"\*\*\[([^\]]+)\]\*\*\s*$")
TOKEN_RE = re.compile(r"^(?:S\d+(?:–S\d+)?|X|E|A|I|N)$")
SRC_RE = re.compile(r"\bS(\d{1,3})\b")


@dataclass(frozen=True)
class Finding:
    rule: str
    where: str
    message: str


def on(rule: str) -> bool:
    return rule not in MUT


def known_sources(register_text: str) -> set[int]:
    return {int(m) for m in re.findall(r"SRC-(\d{3})", register_text)}


def lint_bank(text: str, sources: set[int]) -> list[Finding]:
    out: list[Finding] = []
    lines = text.splitlines()
    qs: list[tuple[str, int, str, str, str | None]] = []  # id, chapter, difficulty, question, answer
    for i, line in enumerate(lines):
        m = Q_RE.match(line)
        if not m:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        am = A_RE.match(nxt)
        qs.append((m.group(1), int(m.group(2)), m.group(3), m.group(4), am.group(1) if am else None))
    ids = [q[0] for q in qs]
    if on("B1"):
        if len(set(ids)) != len(ids):
            out.append(Finding("B1", "bank", "duplicate question id"))
        if ids != [f"{n:03d}" for n in range(1, len(ids) + 1)]:
            out.append(Finding("B1", "bank", "ids are not sequential from Q001"))
    seen: dict[str, str] = {}
    for qid, ch, diff, question, ans in qs:
        if on("B2") and not (1 <= ch <= MAX_CHAPTER):
            out.append(Finding("B2", f"Q{qid}", f"chapter pointer {ch} does not exist"))
        if on("B2") and diff not in DIFFICULTIES:
            out.append(Finding("B2", f"Q{qid}", f"unknown difficulty {diff!r}"))
        if on("B3") and (ans is None or len(ans) < MIN_ANSWER_CHARS):
            out.append(Finding("B3", f"Q{qid}", "missing or too-short answer"))
        if ans is not None:
            tag = TAG_RE.search(ans)
            if on("B4"):
                tokens = [t.strip() for t in tag.group(1).split(",")] if tag else []
                if not tokens or not all(TOKEN_RE.match(t) for t in tokens):
                    out.append(Finding("B4", f"Q{qid}", "answer lacks a valid evidence tag"))
            if on("B7"):
                for s in SRC_RE.findall(ans):
                    if int(s) not in sources:
                        out.append(Finding("B7", f"Q{qid}", f"source S{s} is not in the research register"))
        key = re.sub(r"\W+", " ", question.lower()).strip()
        if on("B5") and key in seen:
            out.append(Finding("B5", f"Q{qid}", f"duplicates Q{seen[key]}"))
        seen[key] = qid
    if on("B6"):
        if len(qs) < MIN_QUESTIONS:
            out.append(Finding("B6", "bank", f"{len(qs)} questions, need at least {MIN_QUESTIONS}"))
        for ch in range(1, MAX_CHAPTER + 1):
            n = sum(1 for q in qs if q[1] == ch)
            if n < MIN_PER_CHAPTER:
                out.append(Finding("B6", f"Ch {ch}", f"{n} questions, need at least {MIN_PER_CHAPTER}"))
    return out


def lint_scenarios(text: str, sources: set[int]) -> list[Finding]:
    out: list[Finding] = []
    parts = re.split(r"^### (SD-\d{2}) — ", text, flags=re.MULTILINE)
    ids = parts[1::2]
    bodies = parts[2::2]
    if on("S1"):
        expected = [f"SD-{n:02d}" for n in range(1, len(ids) + 1)]
        if ids != expected:
            out.append(Finding("S1", "guide", "scenario ids are not sequential from SD-01"))
        if not SCENARIO_RANGE[0] <= len(ids) <= SCENARIO_RANGE[1]:
            out.append(Finding("S1", "guide", f"{len(ids)} scenarios, expected {SCENARIO_RANGE[0]} to {SCENARIO_RANGE[1]}"))
    for sid, body in zip(ids, bodies, strict=True):
        body = re.split(r"^## ", body, flags=re.MULTILINE)[0]  # stop at the next chapter section
        if on("S2"):
            for f in SCENARIO_FIELDS:
                if f"**{f}.**" not in body:
                    out.append(Finding("S2", sid, f"missing field {f}"))
        m = re.search(r"\*\*Draws on\.\*\* (.+)", body)
        if on("S3") and m:
            nums = [int(n) for n in re.findall(r"\d+", re.sub(r"ADR-\d+|OI-\d+", "", m.group(1)))]
            if not nums or any(not 1 <= n <= MAX_CHAPTER for n in nums):
                out.append(Finding("S3", sid, "Draws on cites a chapter that does not exist"))
        if on("S4"):
            for s in SRC_RE.findall(body):
                if int(s) not in sources:
                    out.append(Finding("S4", sid, f"source S{s} is not in the research register"))
    return out


# ---------------------------------------------------------------- A. unit tests on constructed input

def _good_bank(n: int = 100) -> str:
    rows = []
    for i in range(1, n + 1):
        ch = (i - 1) % MAX_CHAPTER + 1
        rows.append(f"**Q{i:03d} [Ch {ch} · {DIFFICULTIES[i % 3]}]** Unique question number {i} about topic {i * 7}?\n"
                    f"**A.** This is a sufficiently long constructed answer for question {i}, with an evidence tag. **[S1, E]**\n")
    return "\n".join(rows)


def _good_scenarios(n: int = 15) -> str:
    one = ("### SD-{n:02d} — Title\n\n**Prompt.** p\n\n**Clarify first.** c\n\n**Model architecture.** m [S1]\n\n"
           "**Trade-offs.** t\n\n**Failure modes.** f\n\n**Probes.** q\n\n**Scoring focus.** s\n\n"
           "**Draws on.** Chapters 1, 5; ADR-012.\n\n")
    return "".join(one.format(n=i) for i in range(1, n + 1))


SOURCES = {1, 2, 3}


def unit_tests() -> None:
    assert lint_bank(_good_bank(), SOURCES) == [], lint_bank(_good_bank(), SOURCES)
    assert lint_scenarios(_good_scenarios(), SOURCES) == []

    def fires(rule: str, findings: list[Finding]) -> None:
        got = {f.rule for f in findings}
        assert rule in got, (rule, findings)
        assert got == {rule}, (rule, got)

    b = _good_bank()
    fires("B1", lint_bank(b.replace("**Q005 ", "**Q006 "), SOURCES))  # duplicate id and a gap at once
    fires("B2", lint_bank(b.replace("[Ch 2 ·", "[Ch 99 ·", 1), SOURCES))
    fires("B3", lint_bank(b.replace("**A.** This is a sufficiently long constructed answer for question 7, with an "
                                    "evidence tag. **[S1, E]**", "**A.** short **[E]**"), SOURCES))
    fires("B4", lint_bank(b.replace("question 8, with an evidence tag. **[S1, E]**", "question 8, with no tag."), SOURCES))
    fires("B5", lint_bank(b.replace("Unique question number 9 about topic 63?", "Unique question number 8 about topic 56?"), SOURCES))
    fires("B6", lint_bank(_good_bank(99), SOURCES))
    fires("B7", lint_bank(b.replace("**[S1, E]**", "**[S9, E]**", 1), SOURCES))
    # per-chapter minimum: drop every question for chapter 31 (ids stay sequential)
    few = _good_bank(93)  # chapters 1..31 each appear three times for n=93; n=100 gives seven chapters four times
    assert lint_bank(few, SOURCES) and {f.rule for f in lint_bank(few, SOURCES)} == {"B6"}

    s = _good_scenarios()
    fires("S1", lint_scenarios(_good_scenarios(14), SOURCES))
    fires("S1", lint_scenarios(s.replace("### SD-03 —", "### SD-04 —", 1), SOURCES))
    fires("S2", lint_scenarios(s.replace("**Probes.** q\n\n", "", 1), SOURCES))
    fires("S3", lint_scenarios(s.replace("Chapters 1, 5; ADR-012.", "Chapters 1, 77.", 1), SOURCES))
    fires("S4", lint_scenarios(s.replace("m [S1]", "m [S50]", 1), SOURCES))
    # awkward input: identifiers like ADR-012 and OI-069 inside "Draws on" must not be read as chapters
    assert lint_scenarios(s.replace("Chapters 1, 5; ADR-012.", "Chapters 1, 5; ADR-012; OI-069.", 1), SOURCES) == []
    print("  unit tests: ok")


# ---------------------------------------------------------------- C. mutation check

def mutants() -> None:
    survived = []
    for rule in ("B1", "B2", "B3", "B4", "B5", "B6", "B7", "S1", "S2", "S3", "S4"):
        MUT.add(rule)
        try:
            unit_tests()
        except AssertionError:
            print(f"  mutant killed: rule {rule} switched off")
        else:
            survived.append(rule)
        finally:
            MUT.discard(rule)
    assert not survived, f"mutants survived: {survived}"
    print(f"  mutation check: {11}/{11} killed")


# ---------------------------------------------------------------- B. the real run

def real_run() -> int:
    chapters = ROOT / "docs" / "chapters"
    register = (ROOT / "project-management" / "RESEARCH-REGISTER.md").read_text(encoding="utf-8")
    sources = known_sources(register)
    guide = next(chapters.glob("32-*.md")).read_text(encoding="utf-8")
    bank = next(chapters.glob("33-*.md")).read_text(encoding="utf-8")
    findings = lint_scenarios(guide, sources) + lint_bank(bank, sources)
    nq = sum(1 for line in bank.splitlines() if Q_RE.match(line))
    ns = len(re.findall(r"^### SD-\d{2} — ", guide, flags=re.MULTILINE))
    print(f"  real run: {ns} scenarios, {nq} questions, {len(sources)} registered sources")
    for f in findings:
        print(f"  FINDING {f.rule} {f.where}: {f.message}")
    print(f"  findings: {len(findings)}")
    return 1 if findings else 0


if __name__ == "__main__":
    print("Chapter 32/33 lint")
    unit_tests()
    if "--mutants" in sys.argv:
        mutants()
    sys.exit(real_run())
