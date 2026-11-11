import { classifyLine } from "./outputLines";

describe("exercise output classification", () => {
  it.each([
    ["== A. BM25 behaviours ==", "heading"],
    ["k1=0 -> score == IDF, independent of tf: OK", "ok"],
    ["All assertions passed.", "pass"],
    ["Traceback (most recent call last):", "error"],
    ["* character-trigram stand-in; not a real embedding model.", "note"],
    ["why did we drop kafka   bm25          0.76   ['d1']", "table"],
    ["plain words", "plain"],
  ])("%s -> %s", (line, kind) => {
    expect(classifyLine(line)).toBe(kind);
  });
});
