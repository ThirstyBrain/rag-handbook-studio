import type { GlossaryTerm, Reference } from "../types";
import { slugify } from "./text";

/** Parses "| **Term** | Definition. [Ch. 2, 9] |" rows from docs/11-Glossary.md. */
export function parseGlossary(md: string): GlossaryTerm[] {
  const terms: GlossaryTerm[] = [];
  for (const line of md.split(/\r?\n/)) {
    const m = /^\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|\s*$/.exec(line);
    if (!m) continue;
    const raw = m[2]!;
    const note = /\[Ch\.\s*([^\]]+)\]\s*$/.exec(raw);
    const chapters = note ? [...note[1]!.matchAll(/\b(\d{1,2})\b/g)].map((x) => Number(x[1])) : [];
    terms.push({
      term: m[1]!,
      slug: slugify(m[1]!),
      definition: (note ? raw.slice(0, note.index) : raw).trim(),
      chapters: [...new Set(chapters)].sort((a, b) => a - b),
    });
  }
  // The handbook may define a term again in a later chapter. Keep every entry; give repeats a
  // unique slug so anchors and list keys stay distinct ("bm25", "bm25-2").
  const seen = new Map<string, number>();
  for (const t of terms) {
    const n = (seen.get(t.slug) ?? 0) + 1;
    seen.set(t.slug, n);
    if (n > 1) t.slug = `${t.slug}-${n}`;
  }
  return terms.sort((a, b) => a.term.localeCompare(b.term, "en", { sensitivity: "base" }));
}

const URL_RE = /(https?:\/\/[^\s)]+)/;

/**
 * References come from two places: the cumulative table in docs/12-References.md
 * ("| S5 | citation | status |") and each chapter's "## References" list ("- [S5] citation").
 * Table entries win; chapter lists fill the gaps for chapters added after the last table update.
 */
export function parseReferences(referencesMd: string, chapterMds: string[]): Map<string, Reference> {
  const refs = new Map<string, Reference>();
  const clean = (s: string) => s.replace(/\s+/g, " ").trim();
  for (const line of referencesMd.split(/\r?\n/)) {
    const m = /^\|\s*(S\d+)\s*\|\s*(.+?)\s*\|\s*([^|]*?)\s*\|\s*$/.exec(line);
    if (!m) continue;
    refs.set(m[1]!, { id: m[1]!, citation: clean(m[2]!), url: URL_RE.exec(m[2]!)?.[1], status: m[3] || undefined });
  }
  for (const md of chapterMds) {
    const idx = md.search(/^## References\s*$/m);
    if (idx < 0) continue;
    for (const m of md.slice(idx).matchAll(/^-\s*\[(S\d+)\]\s*(.+)$/gm)) {
      if (refs.has(m[1]!)) continue;
      refs.set(m[1]!, { id: m[1]!, citation: clean(m[2]!), url: URL_RE.exec(m[2]!)?.[1] });
    }
  }
  return refs;
}
