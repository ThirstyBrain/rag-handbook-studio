import { getHandbook } from "../handbook";

/** Integration: the real handbook repository parses into a coherent model. */
describe("the real handbook", () => {
  const hb = getHandbook();

  it("finds the written chapters with structure and metadata", () => {
    expect(hb.chapters.length).toBeGreaterThanOrEqual(15);
    for (const c of hb.chapters) {
      expect(c.title, c.sourcePath).not.toBe("");
      expect(c.sections.length, c.sourcePath).toBeGreaterThan(0);
      expect(c.partId, c.sourcePath).toMatch(/^part-/);
    }
    const numbers = hb.chapters.map((c) => c.number);
    expect(numbers).toEqual([...numbers].sort((a, b) => a - b));
  });

  it("reads all parts and planned entries from MASTER-TOC", () => {
    expect(hb.parts).toHaveLength(8);
    expect(hb.entries.length).toBeGreaterThanOrEqual(33);
  });

  it("parses every ADR with a status and a decision", () => {
    expect(hb.adrs.length).toBeGreaterThanOrEqual(10);
    for (const a of hb.adrs) {
      expect(a.status, a.id).toMatch(/^[A-Z][a-z]+$/);
      expect(
        a.sections.some((s) => s.kind === "decision"),
        a.id,
      ).toBe(true);
    }
  });

  it("parses glossary, references, diagrams and exercises", () => {
    expect(hb.glossary.length).toBeGreaterThan(50);
    expect(hb.references.get("S67")?.citation).toMatch(/Reciprocal Rank Fusion/);
    expect(hb.diagrams.has("09-hybrid-search-flow.mmd")).toBe(true);
    expect(hb.exercises.find((e) => e.file === "ch10_query_transform.py")?.helpers).toEqual(["_toy_ir.py"]);
  });

  it("has a captured run for every exercise, all exiting cleanly", () => {
    for (const e of hb.exercises) {
      expect(e.runs.length, e.file).toBeGreaterThan(0);
      for (const r of e.runs) expect(r.exitCode, `${e.file} ${r.args}`).toBe(0);
    }
  });
});
