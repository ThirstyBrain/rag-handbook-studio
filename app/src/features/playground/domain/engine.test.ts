import exerciseSource from "@handbook/docs/exercises/ch09_hybrid_search.py?raw";
import captured from "@/generated/exercise-runs.json";
import { CORPUS, QRELS } from "./corpus";
import { BM25, crc32, rrf } from "./engine";
import { runHybrid } from "./hybrid";

/** Parse the Part C table the real Python run printed: "query  method  nDCG  ['d1', 'd7']". */
function pythonPartC() {
  const run = (captured as { runs: { file: string; args: string; stdout: string }[] }).runs.find((r) => r.file === "ch09_hybrid_search.py" && r.args === "");
  if (!run) throw new Error("No captured run for ch09_hybrid_search.py");
  const rows: { query: string; method: string; ndcg: number; top3: string[] }[] = [];
  for (const line of run.stdout.split("\n")) {
    const m = /^(.{24})(bm25|dense\*|rrf|minmax)\s+([\d.]+)\s+\[(.*)\]$/.exec(line);
    if (m) rows.push({ query: m[1]!.trim(), method: m[2]!.replace("*", ""), ndcg: Number(m[3]), top3: [...m[4]!.matchAll(/'(d\d)'/g)].map((x) => x[1]!) });
  }
  return rows;
}

describe("retrieval lab engine (port of ch09_hybrid_search.py Part C)", () => {
  it("uses the same corpus and judgements as the handbook script", () => {
    for (const [id, text] of Object.entries(CORPUS)) expect(exerciseSource).toContain(`"${id}": "${text}"`);
    for (const q of Object.keys(QRELS)) expect(exerciseSource).toContain(`"${q}": {`);
  });

  it("computes zlib-compatible CRC32", () => {
    expect(crc32("The quick brown fox jumps over the lazy dog")).toBe(0x414fa339);
    expect(crc32("")).toBe(0);
  });

  it("reproduces every top-3 list and nDCG@3 from the captured Python run", () => {
    const rows = pythonPartC();
    expect(rows).toHaveLength(16);
    for (const row of rows) {
      const r = runHybrid(row.query);
      const list = row.method === "bm25" ? r.lexical : row.method === "dense" ? r.dense : row.method === "rrf" ? r.rrf : r.minmax;
      expect(list.slice(0, 3).map((d) => d.id), `${row.query} / ${row.method}`).toEqual(row.top3);
      const key = row.method as "bm25" | "dense" | "rrf" | "minmax";
      expect(r.ndcg[key]!.toFixed(2), `${row.query} / ${row.method} nDCG`).toBe(row.ndcg.toFixed(2));
    }
  });

  it("matches the BM25 behaviours asserted in Part A", () => {
    const filler = Array.from({ length: 40 }, (_, i) => `w${i}`).join(" ");
    const docs = { tf1: `kafka ${filler}`, tf8: `${"kafka ".repeat(8)}${filler}`, other: `queue ${filler}` };
    const z = new BM25(docs, { k1: 0, b: 0.75 });
    expect(z.explain("kafka", "tf1").score).toBeCloseTo(z.explain("kafka", "tf8").score, 12);
  });

  it("RRF: k=60 favours consensus, k=0 favours a lone top rank (Part B)", () => {
    const l1 = ["A", "n1", "B", "n2"];
    const l2 = ["m1", "m2", "B", "m3"];
    const k0 = new Map(rrf([l1, l2], 0));
    const k60 = new Map(rrf([l1, l2], 60));
    expect(k0.get("A")!).toBeGreaterThan(k0.get("B")!);
    expect(k60.get("B")!).toBeGreaterThan(k60.get("A")!);
  });

  it("returns empty legs for a query with no matches, without throwing", () => {
    const r = runHybrid("zzzz");
    expect(r.lexical).toEqual([]);
    expect(r.qrels).toBeNull();
  });
});
