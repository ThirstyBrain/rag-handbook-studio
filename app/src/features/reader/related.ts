import type { Chapter } from "@/content/types";

/**
 * Related chapters come from the text itself: chapters this one cites ("Chapter 6", "Ch. 6")
 * and chapters that cite this one, ranked by how often. No hand-curated lists.
 */
export function relatedChapters(chapter: Chapter, all: Chapter[], limit = 4): { chapter: Chapter; weight: number; direction: "cites" | "cited-by" | "both" }[] {
  const mentions = (md: string, n: number) => (md.match(new RegExp(String.raw`\b(?:Chapter|Ch\.)\s*${n}\b`, "g")) ?? []).length;
  return all
    .filter((c) => c.number !== chapter.number)
    .map((c) => {
      const out = mentions(chapter.markdown, c.number);
      const inc = mentions(c.markdown, chapter.number);
      return { chapter: c, weight: out * 2 + inc, direction: (out && inc ? "both" : out ? "cites" : "cited-by") as "cites" | "cited-by" | "both" };
    })
    .filter((r) => r.weight > 0)
    .sort((a, b) => b.weight - a.weight || a.chapter.number - b.chapter.number)
    .slice(0, limit);
}
