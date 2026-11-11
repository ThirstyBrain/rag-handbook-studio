import { CORPUS, QRELS } from "./corpus";
import { BM25, byScoreThenId, cosine, DEFAULT_BM25, linearMinmax, ndcgAtK, rrf, trigramVec, type Bm25Params, type TermContribution } from "./engine";

export interface HybridSettings {
  bm25: Bm25Params;
  /** RRF constant. 60 in the exercise and the original paper. */
  k: number;
  /** Candidates taken from each leg before fusion (8 in the exercise = the whole corpus). */
  candidateK: number;
  /** Per-leg weights [lexical, dense]; 1 and 1 in the exercise. */
  weights: [number, number];
}

export const DEFAULT_SETTINGS: HybridSettings = { bm25: DEFAULT_BM25, k: 60, candidateK: 8, weights: [1, 1] };

export interface RankedDoc {
  id: string;
  score: number;
  rank: number;
}

export interface LexicalHit extends RankedDoc {
  terms: TermContribution[];
}

export type Method = "bm25" | "dense" | "rrf" | "minmax";

export interface HybridResult {
  query: string;
  lexical: LexicalHit[];
  dense: RankedDoc[];
  rrf: RankedDoc[];
  minmax: RankedDoc[];
  /** Relevance judgements when the query is one of the exercise's four judged queries. */
  qrels: Record<string, number> | null;
  ndcg: Partial<Record<Method, number>>;
  queryTokens: string[];
}

const ranked = (pairs: [string, number][]): RankedDoc[] => pairs.map(([id, score], i) => ({ id, score, rank: i + 1 }));

const docVectors = new Map(Object.entries(CORPUS).map(([d, t]) => [d, trigramVec(t)]));

/** Runs the exercise's Part C pipeline for one query. Defaults reproduce the script exactly. */
export function runHybrid(query: string, settings: HybridSettings = DEFAULT_SETTINGS): HybridResult {
  const bm = new BM25(CORPUS, settings.bm25);
  const lexPairs = bm.rank(query);
  const lexScores = new Map(lexPairs);
  const lexical: LexicalHit[] = lexPairs.map(([id, score], i) => ({ id, score, rank: i + 1, terms: bm.explain(query, id).terms }));

  const qv = trigramVec(query);
  const denPairs = [...docVectors].map(([d, v]): [string, number] => [d, cosine(qv, v)]).sort(byScoreThenId).filter(([, s]) => s > 0);
  const lexIds = lexPairs.map(([d]) => d);
  const denIds = denPairs.map(([d]) => d);

  const fused = rrf([lexIds.slice(0, settings.candidateK), denIds.slice(0, settings.candidateK)], settings.k, settings.weights);
  const denTop = new Map(denPairs.slice(0, settings.candidateK));
  const lin = linearMinmax(lexScores, denTop, settings.weights[0], settings.weights[1]);

  const qrels = QRELS[query] ?? null;
  const result: HybridResult = {
    query,
    lexical,
    dense: ranked(denPairs),
    rrf: ranked(fused),
    minmax: ranked(lin),
    qrels,
    ndcg: {},
    queryTokens: [...new Set(query.toLowerCase().match(/[a-z0-9]+/g) ?? [])],
  };
  if (qrels) {
    result.ndcg = {
      bm25: ndcgAtK(lexIds, qrels),
      dense: ndcgAtK(denIds, qrels),
      rrf: ndcgAtK(result.rrf.map((r) => r.id), qrels),
      minmax: ndcgAtK(result.minmax.map((r) => r.id), qrels),
    };
  }
  return result;
}
