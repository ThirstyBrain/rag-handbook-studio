import { marked, type Token, type Tokens } from "marked";
import { getHandbook } from "../handbook";
import { handbookRenderContext } from "../renderContext";
import { renderMarkdown } from "@/shared/markdown/render";

/**
 * Content fidelity: every chapter's rendered page must contain everything in its Markdown source.
 * Compared per element type, and per text block (paragraphs, list items, headings, table cells).
 */
const norm = (s: string) => s.replace(/[[\]`*_,\s]/g, "");
const RUN_LINE = /^python3?\s+(?:-I\s+)?(?:docs\/exercises\/)?ch\d+_[a-z0-9_]+\.py(?:\s+--[a-z-]+)*\s*$/;

function collect(tokens: Token[], acc: { texts: string[]; counts: Record<string, number> }) {
  for (const t of tokens) {
    acc.counts[t.type] = (acc.counts[t.type] ?? 0) + 1;
    if (t.type === "paragraph" || t.type === "text" || t.type === "heading") {
      acc.texts.push(new DOMParser().parseFromString(marked.parseInline((t as { text: string }).text) as string, "text/html").body.textContent ?? "");
    }
    if (t.type === "table") {
      const tb = t as Tokens.Table;
      for (const c of [...tb.header, ...tb.rows.flat()]) acc.texts.push(c.text);
    }
    if (t.type === "list") {
      for (const it of (t as Tokens.List).items) {
        acc.counts.list_item = (acc.counts.list_item ?? 0) + 1;
        collect(it.tokens, acc);
      }
    } else if ((t as { tokens?: Token[] }).tokens && t.type !== "paragraph" && t.type !== "heading") {
      collect((t as { tokens: Token[] }).tokens, acc);
    }
  }
}

describe.each(getHandbook().chapters.map((c) => [c.slug, c] as const))("chapter %s renders all of its content", (_slug, chapter) => {
  const tokens = marked.lexer(chapter.markdown);
  const acc = { texts: [] as string[], counts: {} as Record<string, number> };
  collect(tokens.slice(1), acc); // the H1 is rendered by the page header
  const { html, exerciseSlots } = renderMarkdown(chapter.markdown, handbookRenderContext());
  const doc = new DOMParser().parseFromString(html, "text/html");
  const out = norm(doc.body.textContent ?? "");
  const codes = tokens.filter((t): t is Tokens.Code => t.type === "code");
  const mermaid = codes.filter((c) => c.lang === "mermaid").length;
  const runBlocks = codes.filter((c) => c.lang !== "mermaid" && c.text.split("\n").filter((l) => l.trim()).every((l) => RUN_LINE.test(l.trim()))).length;

  it("keeps every paragraph, list item, heading and table cell", () => {
    const missing = acc.texts.map(norm).filter((t) => t && !out.includes(t));
    expect(missing).toEqual([]);
  });

  it("keeps every heading, table, list item and callout", () => {
    expect(doc.querySelectorAll("h2,h3,h4,h5,h6").length).toBe(acc.counts.heading ?? 0);
    expect(doc.querySelectorAll("table").length).toBe(acc.counts.table ?? 0);
    expect(doc.querySelectorAll("li").length).toBe(acc.counts.list_item ?? 0);
    expect(doc.querySelectorAll("aside.callout").length).toBe(acc.counts.blockquote ?? 0);
  });

  it("renders every diagram and every code block", () => {
    expect(doc.querySelectorAll("figure.diagram").length).toBe(mermaid);
    expect(doc.querySelectorAll(".code").length).toBe(codes.length - mermaid - runBlocks);
  });

  it("shows code and captured output for every exercise it cites", () => {
    const placed = new Set(exerciseSlots.map((s) => s.file));
    expect([...chapter.exercises].filter((f) => !placed.has(f))).toEqual([]);
    for (const s of exerciseSlots) expect(getHandbook().exercises.find((e) => e.file === s.file)?.runs.length, s.file).toBeGreaterThan(0);
  });
});
