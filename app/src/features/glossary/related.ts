import type { GlossaryTerm } from "@/content/types";

/** Short forms used for matching: "ANN (approximate nearest neighbour)" -> ["ann", "approximate nearest neighbour"]. */
export function termAliases(term: string): string[] {
  const m = /^(.*?)\s*\((.*)\)\s*$/.exec(term);
  const parts = m ? [m[1]!, m[2]!] : [term];
  return parts.map((p) => p.trim().toLowerCase()).filter((p) => p.length >= 3);
}

/** Terms whose name appears in this term's definition (whole-word match). */
export function relatedTerms(term: GlossaryTerm, all: GlossaryTerm[], limit = 4): GlossaryTerm[] {
  const def = term.definition.toLowerCase();
  return all
    .filter((other) => other.slug !== term.slug)
    .filter((other) => termAliases(other.term).some((a) => new RegExp(String.raw`(^|[^a-z0-9])${a.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}([^a-z0-9]|$)`).test(def)))
    .slice(0, limit);
}
