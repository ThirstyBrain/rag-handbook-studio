import { renderMarkdown } from "./render";

const FENCE = "```";
const ctx = {
  chapterSlugs: new Map([
    [6, "06-retrieval"],
    [9, "09-hybrid-search"],
  ]),
  adrIds: new Set(["ADR-004"]),
  exercises: new Set(["ch09_hybrid_search.py"]),
  skipH1: true,
};

describe("renderMarkdown", () => {
  it("turns evidence tags into labelled marks and source links", () => {
    const { html } = renderMarkdown("A claim [E, S67] and a run [X].", ctx);
    expect(html).toContain('data-source="S67"');
    expect(html).toContain('class="ev ev--e"');
    expect(html).toContain('class="ev ev--x"');
  });

  it("links ADR and chapter mentions that exist, and only those", () => {
    const { html } = renderMarkdown("See ADR-004, ADR-099, Chapter 6 and Chapter 30.", ctx);
    expect(html).toContain('href="/decisions/ADR-004"');
    expect(html).not.toContain("/decisions/ADR-099");
    expect(html).toContain('href="/handbook/06-retrieval"');
    expect(html).not.toContain("Chapter 30</a>");
  });

  it("gives headings stable, de-duplicated ids and skips the chapter H1", () => {
    const { html } = renderMarkdown("# Chapter 9 — Hybrid\n\n## 9.4.1 BM25\n\n## 9.4.1 BM25\n", ctx);
    expect(html).not.toContain("<h1");
    expect(html).toContain('id="9-4-1-bm25"');
    expect(html).toContain('id="9-4-1-bm25-1"');
  });

  it("highlights code and adds a copy button; wraps tables", () => {
    const { html } = renderMarkdown(`${FENCE}sql\nSELECT 1;\n${FENCE}\n\n| a | b |\n|---|---|\n| 1 | 2 |\n`, ctx);
    expect(html).toContain('data-lang="sql"');
    expect(html).toContain("data-copy");
    expect(html).toContain('class="table-wrap"');
  });

  it("turns mermaid blocks into lazy diagram figures with a source fallback", () => {
    const { html } = renderMarkdown(`${FENCE}mermaid\nflowchart TD\n  A --> B\n${FENCE}`, ctx);
    expect(html).toContain('class="diagram"');
    expect(html).toContain("data-mermaid=");
    expect(html).toContain("flowchart TD");
  });

  it("replaces run blocks with exercise slots, keeping variant arguments", () => {
    const { html, exerciseSlots } = renderMarkdown(`${FENCE}bash\npython -I docs/exercises/ch09_hybrid_search.py\npython -I docs/exercises/ch09_hybrid_search.py --mutants\n${FENCE}`, ctx);
    expect(exerciseSlots).toEqual([
      { file: "ch09_hybrid_search.py", args: "" },
      { file: "ch09_hybrid_search.py", args: "--mutants" },
    ]);
    expect(html).not.toContain("<pre>");
  });

  it("places one panel after the first mention of an exercise that is never run", () => {
    const { exerciseSlots, html } = renderMarkdown("Run `docs/exercises/ch09_hybrid_search.py` now.\n\nAgain `ch09_hybrid_search.py`.", ctx);
    expect(exerciseSlots).toHaveLength(1);
    expect(html).toContain('href="#exercise-ch09_hybrid_search"');
  });

  it("sanitises raw HTML in the source", () => {
    const { html } = renderMarkdown('<img src=x onerror="alert(1)"> <script>alert(1)</script>', ctx);
    expect(html).not.toContain("onerror");
    expect(html).not.toContain("<script");
  });
});
