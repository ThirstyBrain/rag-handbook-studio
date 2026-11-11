import { getHandbook } from "@/content/handbook";
import { buildSearchDocs, makeSnippet, SearchIndex, tokenize } from "./searchIndex";

describe("search index over the real handbook", () => {
  const docs = buildSearchDocs(getHandbook());
  const index = new SearchIndex(docs);

  it("indexes chapters, sections, terms, decisions, exercises and sources", () => {
    expect([...new Set(docs.map((d) => d.kind))].sort()).toEqual(["chapter", "decision", "exercise", "reference", "section", "term"]);
  });

  it("finds the RRF material for a multi-word query", () => {
    const hits = index.search("reciprocal rank fusion");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits.slice(0, 8).some((h) => /fusion|RRF|Reciprocal/i.test(h.doc.title + h.doc.text))).toBe(true);
  });

  it("matches the last word as a prefix while typing", () => {
    expect(index.search("hybr").length).toBeGreaterThan(0);
  });

  it("requires every word to match", () => {
    expect(index.search("zzzqqq bm25")).toEqual([]);
  });

  it("returns nothing for an empty query", () => {
    expect(index.search("   ")).toEqual([]);
  });

  it("finds an exact identifier like an ADR id", () => {
    expect(index.search("ADR-004").some((h) => h.doc.href === "/decisions/ADR-004")).toBe(true);
  });

  it("tokenises hyphenated identifiers both whole and in parts", () => {
    expect(tokenize("cross-encoder E-4471")).toEqual(["cross-encoder", "cross", "encoder", "e-4471", "e", "4471"]);
  });

  it("builds snippets with highlight ranges", () => {
    const s = makeSnippet("The quick brown fox jumps over the lazy dog", ["fox"]);
    expect(s.text.slice(s.marks[0]![0], s.marks[0]![1])).toBe("fox");
  });
});
