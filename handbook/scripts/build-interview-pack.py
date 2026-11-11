"""Generate the interview package from Chapters 32 and 33 (single source of truth: the chapters).

Outputs (all GENERATED; never edit by hand):
  docs/07-System-Design-Interview-Guide.md   <- Ch. 32 sections 32.4-32.8 (method, rubric, scenarios, pitfalls)
  docs/08-Interview-Question-Bank.md         <- Ch. 33 sections 33.4-33.5 (+ evidence legend)
  docs/flashcards/rag-flashcards.md          <- one collapsible card per question
  docs/flashcards/rag-flashcards.tsv         <- Anki-importable (front<TAB>back<TAB>tags)

No new technical claims are introduced here: every card is a verbatim question/answer pair from Ch. 33.
Exit code 1 if the parsed counts disagree with the chapter (guards against a silent format change).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH32 = ROOT / "docs" / "chapters" / "32-system-design-interview-preparation.md"
CH33 = ROOT / "docs" / "chapters" / "33-advanced-interview-question-bank.md"
DOCS = ROOT / "docs"
CARD = re.compile(
    r"\*\*(Q\d{3}) \[Ch ([\d–\-, ]+) · (foundational|intermediate|advanced)\]\*\* (.+?)\r?\n\*\*A\.\*\* (.+?)(?=\r?\n\r?\n|\Z)",
    re.S,
)


def section(text: str, start: str, end: str) -> str:
    """Text from the heading starting with `start` up to (excluding) the heading starting with `end`."""
    m = re.search(rf"^## {re.escape(start)}.*?(?=^## {re.escape(end)})", text, re.S | re.M)
    if not m:
        raise SystemExit(f"section {start!r}..{end!r} not found")
    return m.group(0).rstrip() + "\n"


def header(title: str, source: str) -> str:
    return (
        f"# {title}\n\n"
        f"> GENERATED FILE. Source of truth: `docs/chapters/{source}`. "
        f"Rebuild with `python -I scripts/build-interview-pack.py`.\n\n"
    )


def main() -> int:
    t32 = CH32.read_text(encoding="utf-8")
    t33 = CH33.read_text(encoding="utf-8")

    legend = re.search(r"^> \*\*Evidence legend\.\*\*.*$", t33, re.M)
    if not legend:
        raise SystemExit("evidence legend not found in Ch. 33")

    guide = header("System Design Interview Guide", CH32.name) + section(t32, "32.4", "32.9")
    bank = (
        header("Advanced Interview Question Bank", CH33.name)
        + legend.group(0) + "\n\n"
        + section(t33, "33.4", "33.6")
    )
    (DOCS / "07-System-Design-Interview-Guide.md").write_text(guide, encoding="utf-8", newline="\n")
    (DOCS / "08-Interview-Question-Bank.md").write_text(bank, encoding="utf-8", newline="\n")

    cards = CARD.findall(t33)
    declared = len(re.findall(r"^\*\*Q\d{3} \[", t33, re.M))
    if len(cards) != declared:
        print(f"FAIL parsed {len(cards)} cards but chapter has {declared} questions", file=sys.stderr)
        return 1

    fdir = DOCS / "flashcards"
    fdir.mkdir(exist_ok=True)
    md = [
        "# RAG Flashcards\n\n",
        f"> GENERATED FILE from `docs/chapters/{CH33.name}` ({len(cards)} cards). "
        "Cover the answer, say yours aloud, then expand. Evidence tags are defined in the "
        "[question bank](../08-Interview-Question-Bank.md). Rebuild: `python -I scripts/build-interview-pack.py`.\n",
    ]
    tsv: list[str] = []
    for qid, chap, level, q, a in cards:
        a = " ".join(a.split())
        q = " ".join(q.split())
        md.append(
            f"\n<details><summary><b>{qid}</b> · Ch {chap} · {level}: {q}</summary>\n\n{a}\n\n</details>\n"
        )
        tag = f"rag ch{chap.split('–')[0].split('-')[0].strip()} {level}"
        tsv.append(f"{qid}: {q}\t{a}\t{tag}")
    (fdir / "rag-flashcards.md").write_text("".join(md), encoding="utf-8", newline="\n")
    (fdir / "rag-flashcards.tsv").write_text("\n".join(tsv) + "\n", encoding="utf-8", newline="\n")

    scenarios = re.split(r"^(?=### SD-\d\d)", section(t32, "32.6", "32.7"), flags=re.M)[1:]
    mock = [
        "# Mock Interview Sheets\n\n",
        f"> GENERATED FILE from `docs/chapters/{CH32.name}` ({len(scenarios)} scenarios). "
        "Prompt, probes and scoring focus are verbatim from the chapter; the session plan below is an "
        "engineering suggestion **[E]**, not a measured or sourced norm. Rebuild: `python -I scripts/build-interview-pack.py`.\n\n"
        "## How to run a session\n\n"
        "1. Interviewer reads only **Prompt**; candidate asks clarifying questions (check against **Clarify first**).\n"
        "2. Candidate states the security boundary and a sizing approach, then the architecture (method: Chapter 32.4).\n"
        "3. Interviewer uses **Probes** one at a time; after the session, score against the rubric (Chapter 32.5) "
        "weighting the **Scoring focus**.\n"
        "4. Compare with the model answer in the scenario (Chapter 32.6) and read the chapters in **Draws on**.\n",
    ]
    for block in scenarios:
        title = block.splitlines()[0].removeprefix("### ")
        fields = {}
        for label in ("Prompt", "Clarify first", "Probes", "Scoring focus", "Draws on"):
            m = re.search(rf"^\*\*{label}\.\*\* (.+)$", block, re.M)
            if not m:
                print(f"FAIL {title}: missing field {label}", file=sys.stderr)
                return 1
            fields[label] = m.group(1)
        mock.append(f"\n## {title}\n\n**Prompt.** {fields['Prompt']}\n\n")
        mock.append(f"**Probes.** {fields['Probes']}\n\n**Scoring focus.** {fields['Scoring focus']}\n\n")
        mock.append(f"<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>\n\n")
        mock.append(f"**Clarify first.** {fields['Clarify first']}\n\n**Draws on.** {fields['Draws on']}\n\n</details>\n")
    (DOCS / "exercises" / "mock-interviews.md").write_text("".join(mock), encoding="utf-8", newline="\n")

    sheet = [
        "# Cheat Sheet: Chapter Summaries\n\n",
        "> GENERATED FILE. Each section is the verbatim Summary of the chapter named in its heading; "
        "claims and evidence tags are as in the chapter. Rebuild: `python -I scripts/build-interview-pack.py`.\n",
    ]
    count = 0
    for ch in sorted((DOCS / "chapters").glob("[0-9][0-9]-*.md")):
        txt = ch.read_text(encoding="utf-8")
        title = re.match(r"# (.+)", txt).group(1).strip()
        m = re.search(r"^## \d+\.\d+ Summary\s*$(.*?)(?=^## |\Z)", txt, re.S | re.M)
        if not m:
            print(f"WARN no Summary in {ch.name}", file=sys.stderr)
            continue
        count += 1
        sheet.append(f"\n## {title}\n\n{m.group(1).strip()}\n")
    (DOCS / "cheat-sheets" / "chapter-summaries.md").write_text("".join(sheet), encoding="utf-8", newline="\n")

    print(f"guide + bank written; flashcards={len(cards)}; mock scenarios={len(scenarios)}; summaries={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
