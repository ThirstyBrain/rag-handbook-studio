import { parseAdr, adrSectionKind } from "../parse/adr";
import { parseChapter } from "../parse/chapter";
import { countEvidence, parseEvidenceTag } from "../parse/evidence";
import { parseGlossary, parseReferences } from "../parse/glossary";
import { parseMasterToc } from "../parse/toc";
import { firstSentence, slugify, splitByHeadings, toPlainText } from "../parse/text";

const FENCE = "```";

describe("text helpers", () => {
  it("slugifies numbered headings the same way the renderer does", () => {
    expect(slugify("9.4.1 BM25")).toBe("9-4-1-bm25");
    expect(slugify("Practical Example (Illustrative, Executed [X])")).toBe("practical-example-illustrative-executed-x");
  });
  it("ignores # lines inside fenced code when splitting", () => {
    const blocks = splitByHeadings(`# T\n## A\n${FENCE}bash\n# not a heading\n${FENCE}\n## B\n`);
    expect(blocks.filter((b) => b.heading).map((b) => b.heading!.text)).toEqual(["T", "A", "B"]);
  });
  it("strips Markdown for previews", () => {
    expect(toPlainText("**Bold** and `code` and [link](http://x)")).toBe("Bold and code and link");
  });
  it("takes the first sentence only", () => {
    expect(firstSentence("Dense retrieval matches meaning. Lexical matches terms.")).toBe("Dense retrieval matches meaning.");
    expect(firstSentence("No full stop here")).toBe("No full stop here");
  });
});

describe("evidence tags", () => {
  it("parses combined tags", () => {
    expect(parseEvidenceTag("E, S76")).toEqual([{ kind: "E" }, { kind: "S", ref: "S76" }]);
  });
  it("counts tags outside code and ignores Markdown links", () => {
    const md = `A [X] claim [E, S5]. A [link](http://x). ${FENCE}\n[X]\n${FENCE}`;
    expect(countEvidence(md)).toEqual({ X: 1, E: 1, S: 1 });
  });
});

describe("MASTER-TOC", () => {
  const md = [
    "## Part I — RAG Fundamentals (M2)",
    "",
    "| # | Chapter | Batch | Status |",
    "|---|---|---|---|",
    "| 1 | Traditional LLM vs. RAG | B1 | complete (with recorded limitations OI-010) |",
    "",
    "## Part IV — Implementation (M5)",
    "",
    "| # | Chapter | Batch | Status |",
    "|---|---|---|---|",
    "| 16 | Build It | M5 | IN PROGRESS (living chapter) |",
    "| 18 | Evaluation | B9 | pending |",
    "",
    "## Chapter → Supporting Document Mapping",
    "",
    "| Supporting document | Chapters |",
    "|---|---|",
    "| x | 1–5 |",
  ].join("\n");

  it("reads parts, chapters, statuses and notes", () => {
    const { parts, entries } = parseMasterToc(md);
    expect(parts.map((p) => p.roman)).toEqual(["I", "IV"]);
    expect(entries).toHaveLength(3);
    expect(entries[0]).toMatchObject({ number: 1, status: "complete", statusNote: "with recorded limitations OI-010" });
    expect(entries[1]).toMatchObject({ number: 16, status: "in-progress" });
    expect(entries[2]).toMatchObject({ number: 18, status: "pending" });
  });
});

describe("chapter parser", () => {
  const md = [
    "# Chapter 9 — Hybrid Search",
    "",
    "> legend",
    "",
    "## 9.1 Learning Objectives",
    "",
    "1. Explain **BM25**.",
    "2. Choose a fusion.",
    "",
    "## 9.2 Problem Statement",
    "",
    "Dense retrieval matches meaning. More text [X].",
    "",
    "### 9.2.1 Detail",
    "",
    "See ADR-004 and `docs/exercises/ch09_hybrid_search.py` and diagrams/09-hybrid-search-flow.mmd.",
    "",
    "## 9.17 Summary",
    "",
    "It all fuses.",
  ].join("\n");
  const c = parseChapter("docs/chapters/09-hybrid-search.md", md);

  it("extracts identity and structure", () => {
    expect(c).toMatchObject({ number: 9, title: "Hybrid Search", slug: "09-hybrid-search" });
    expect(c.sections.map((s) => s.id)).toEqual(["9-1-learning-objectives", "9-2-problem-statement", "9-2-1-detail", "9-17-summary"]);
    expect(c.sections[2]).toMatchObject({ level: 3, number: "9.2.1", title: "Detail" });
  });

  it("extracts objectives, problem, summary and cross-references", () => {
    expect(c.objectives).toEqual(["Explain BM25.", "Choose a fusion."]);
    expect(c.problem).toBe("Dense retrieval matches meaning. More text [X].");
    expect(c.summary).toBe("It all fuses.");
    expect(c.adrs).toEqual(["ADR-004"]);
    expect(c.exercises).toEqual(["ch09_hybrid_search.py"]);
    expect(c.diagrams).toEqual(["09-hybrid-search-flow.mmd"]);
    expect(c.evidence.X).toBe(1);
  });
});

describe("ADR parser", () => {
  const md = ["# ADR-004: Retrieval Architecture", "", "## Status", "", "Proposed — 2026-11-07.", "", "## Context", "", "Ctx.", "", "## Decision (proposed)", "", "Do it.", "", "## Amendment 2026-11-07 (Chapter 9)", "", "More."].join("\n");

  it("normalises section kinds and status", () => {
    const a = parseAdr("adr/ADR-004-Retrieval-Architecture.md", md);
    expect(a).toMatchObject({ id: "ADR-004", number: 4, title: "Retrieval Architecture", status: "Proposed" });
    expect(a.sections.map((s) => s.kind)).toEqual(["status", "context", "decision", "amendment"]);
  });
  it("maps headings to kinds", () => {
    expect(adrSectionKind("Evidence gaps")).toBe("gaps");
    expect(adrSectionKind("Something else")).toBe("other");
  });
});

describe("glossary and references", () => {
  it("parses terms, chapter notes and sorts alphabetically", () => {
    const g = parseGlossary("| Term | Definition |\n|---|---|\n| **RAG** | Retrieve then generate. [Ch. 1] |\n| **BM25** | A lexical ranking function. [Ch. 2, 9] |");
    expect(g.map((t) => t.term)).toEqual(["BM25", "RAG"]);
    expect(g[0]).toMatchObject({ slug: "bm25", definition: "A lexical ranking function.", chapters: [2, 9] });
  });
  it("keeps repeated terms and gives each a unique slug", () => {
    const g = parseGlossary("| **BM25** | First. [Ch. 2] |\n| **BM25** | Second. [Ch. 9] |");
    expect(g.map((t) => t.slug).sort()).toEqual(["bm25", "bm25-2"]);
    expect(g.map((t) => t.definition).sort()).toEqual(["First.", "Second."]);
  });
  it("prefers the reference table and falls back to chapter lists", () => {
    const refs = parseReferences("| S5 | Microsoft. Hybrid. https://learn.microsoft.com/x | read |", ["## References\n\n- [S5] other\n- [S67] Cormack et al. http://cormack.uwaterloo.ca/rrf.pdf"]);
    expect(refs.get("S5")).toMatchObject({ status: "read", url: "https://learn.microsoft.com/x" });
    expect(refs.get("S67")?.url).toBe("http://cormack.uwaterloo.ca/rrf.pdf");
  });
});
