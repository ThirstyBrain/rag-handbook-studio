import type { Method } from "./domain/hybrid";

/** Plain text shown on the lab page and in its static snapshot, so both say the same thing. */
export const METHODS: { id: Method; label: string; explain: string }[] = [
  { id: "bm25", label: "Keyword (BM25)", explain: "Scores documents by the query terms they contain: rare terms count more, repeated terms saturate, long documents are normalised." },
  { id: "dense", label: "Semantic stand-in", explain: "Cosine similarity of character-trigram vectors. It rewards shared spelling, which is why it matches “contractor” to “Contractors”; it understands nothing." },
  { id: "rrf", label: "Hybrid, RRF", explain: "Adds 1 / (k + rank) from each leg. It ignores raw scores entirely, so the two legs' incompatible scales never need calibrating." },
  { id: "minmax", label: "Hybrid, min–max", explain: "Rescales each leg's scores to 0–1 and adds them. It keeps magnitude, so one extreme score can compress all the others." },
];

/** "A deterministic port of <file> …" split around the file name, which the page renders as code. */
export const HONESTY = {
  before: "A deterministic port of",
  after:
    "Part C, checked by a unit test against the script's real output. With eight documents it shows the mechanics of fusion. It says nothing about which method wins on real data; the handbook's advice is to measure on your own golden set, per query class.",
};

export const HOW_TO_READ: string[] = [
  "Pick a question. Each leg ranks the eight documents on its own, and the lines between the columns show how every document moves when the two rankings are fused.",
  "Compare the fused ranking with the documents known to be relevant to that question. nDCG@3 summarises how close the top three results are to the ideal order, where 1.0 is perfect.",
  "Change the parameters and watch which documents move. Switch between reciprocal rank fusion and min–max fusion to see how rank-based and score-based fusion can disagree.",
];
