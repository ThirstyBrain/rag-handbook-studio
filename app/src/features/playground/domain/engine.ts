/**
 * A line-for-line TypeScript port of Part C of the handbook exercise
 * `docs/exercises/ch09_hybrid_search.py` (BM25, character-trigram "dense" stand-in, RRF,
 * min–max fusion, nDCG@3). With default parameters it reproduces the script's captured output
 * exactly — see engine.test.ts. It is a toy: eight documents, no real embedding model.
 */

// ---------------------------------------------------------------- tokenisation
export function tokens(s: string): string[] {
  return s.toLowerCase().match(/[a-z0-9]+/g) ?? [];
}

// ---------------------------------------------------------------- BM25
export interface Bm25Params {
  k1: number;
  b: number;
}
export const DEFAULT_BM25: Bm25Params = { k1: 1.2, b: 0.75 };

export interface TermContribution {
  term: string;
  tf: number;
  idf: number;
  score: number;
}

export class BM25 {
  readonly tf = new Map<string, Map<string, number>>();
  readonly len = new Map<string, number>();
  readonly df = new Map<string, number>();
  readonly N: number;
  readonly avg: number;

  constructor(
    docs: Record<string, string>,
    readonly params: Bm25Params = DEFAULT_BM25,
  ) {
    for (const [id, text] of Object.entries(docs)) {
      const counts = new Map<string, number>();
      for (const t of tokens(text)) counts.set(t, (counts.get(t) ?? 0) + 1);
      this.tf.set(id, counts);
      this.len.set(id, [...counts.values()].reduce((a, b) => a + b, 0));
      for (const t of counts.keys()) this.df.set(t, (this.df.get(t) ?? 0) + 1);
    }
    this.N = this.tf.size;
    this.avg = [...this.len.values()].reduce((a, b) => a + b, 0) / this.N;
  }

  idf(term: string): number {
    const n = this.df.get(term) ?? 0;
    return Math.log(1 + (this.N - n + 0.5) / (n + 0.5));
  }

  /** Score with per-term breakdown (the breakdown is what the lab shows as an explanation). */
  explain(query: string, doc: string): { score: number; terms: TermContribution[] } {
    const { k1, b } = this.params;
    let score = 0;
    const terms: TermContribution[] = [];
    const counts = this.tf.get(doc)!;
    for (const t of tokens(query)) {
      const f = counts.get(t) ?? 0;
      if (f === 0) continue;
      const norm = 1 - b + (b * this.len.get(doc)!) / this.avg;
      const s = (this.idf(t) * f * (k1 + 1)) / (f + k1 * norm);
      score += s;
      terms.push({ term: t, tf: f, idf: this.idf(t), score: s });
    }
    return { score, terms };
  }

  rank(query: string): [string, number][] {
    const out: [string, number][] = [];
    for (const d of this.tf.keys()) {
      const s = this.explain(query, d).score;
      if (s > 0) out.push([d, s]);
    }
    return out.sort(byScoreThenId);
  }
}

// ---------------------------------------------------------------- trigram "dense" stand-in
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

/** zlib.crc32 over ASCII bytes. */
export function crc32(s: string): number {
  let c = 0xffffffff;
  for (let i = 0; i < s.length; i++) c = CRC_TABLE[(c ^ s.charCodeAt(i)) & 0xff]! ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export function trigramVec(s: string, dim = 256): number[] {
  const text = " " + s.toLowerCase().replace(/[^a-z0-9]+/g, " ") + " ";
  const v = new Array<number>(dim).fill(0);
  for (let i = 0; i < text.length - 2; i++) v[crc32(text.slice(i, i + 3)) % dim]! += 1;
  return v;
}

export function cosine(a: number[], b: number[]): number {
  const na = Math.sqrt(a.reduce((s, x) => s + x * x, 0));
  const nb = Math.sqrt(b.reduce((s, x) => s + x * x, 0));
  if (!na || !nb) return 0;
  let dot = 0;
  for (let i = 0; i < a.length; i++) dot += a[i]! * b[i]!;
  return dot / (na * nb);
}

// ---------------------------------------------------------------- fusion
export function byScoreThenId(a: [string, number], b: [string, number]): number {
  return b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
}

export function rrf(lists: string[][], k = 60, weights?: number[]): [string, number][] {
  const w = weights ?? lists.map(() => 1);
  const sc = new Map<string, number>();
  lists.forEach((list, li) => list.forEach((d, i) => sc.set(d, (sc.get(d) ?? 0) + w[li]! / (k + i + 1))));
  return [...sc.entries()].sort(byScoreThenId);
}

export function minmax(scores: Map<string, number>): Map<string, number> {
  const vals = [...scores.values()];
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  return new Map([...scores].map(([d, v]) => [d, hi > lo ? (v - lo) / (hi - lo) : 0]));
}

export function linearMinmax(a: Map<string, number>, b: Map<string, number>, wa = 1, wb = 1): [string, number][] {
  const na = a.size ? minmax(a) : new Map<string, number>();
  const nb = b.size ? minmax(b) : new Map<string, number>();
  const docs = new Set([...a.keys(), ...b.keys()]);
  return [...docs].map((d): [string, number] => [d, wa * (na.get(d) ?? 0) + wb * (nb.get(d) ?? 0)]).sort(byScoreThenId);
}

// ---------------------------------------------------------------- metrics
export function ndcgAtK(ranked: string[], rel: Record<string, number>, k = 3): number {
  const dcg = (g: number[]) => g.reduce((s, x, i) => s + x / Math.log2(i + 2), 0);
  const gains = ranked.slice(0, k).map((d) => rel[d] ?? 0);
  const ideal = Object.values(rel)
    .sort((x, y) => y - x)
    .slice(0, k);
  const idcg = dcg(ideal);
  return idcg ? dcg(gains) / idcg : 0;
}
