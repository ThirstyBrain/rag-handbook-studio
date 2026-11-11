import type { Handbook } from "@/content/handbook";
import { toPlainText } from "@/content/parse/text";

/**
 * A small local full-text index over the real handbook content: chapters, sections, glossary
 * terms, ADRs and their sections, exercises and references. Built in memory on first search
 * (a few thousand documents), so there is no server and no third-party service.
 *
 * Scoring: every query term must match (the last term as a prefix, so results update while
 * typing). Title hits weigh more than body hits; body hits use log-tf × idf.
 */
export type SearchKind = "chapter" | "section" | "term" | "decision" | "exercise" | "reference";

export interface SearchDoc {
  id: string;
  kind: SearchKind;
  title: string;
  /** Where the hit lives, e.g. "Chapter 9 — Hybrid Search". */
  context: string;
  text: string;
  href: string;
}

export interface SearchHit {
  doc: SearchDoc;
  score: number;
  snippet: { text: string; marks: [number, number][] };
}

interface Entry {
  doc: SearchDoc;
  title: Set<string>;
  tf: Map<string, number>;
}

export function stemToken(t: string): string {
  return t.length > 3 && t.endsWith("s") && !t.endsWith("ss") ? t.slice(0, -1) : t;
}

export function tokenize(s: string): string[] {
  return (s.toLowerCase().match(/[a-z0-9]+(?:[-_][a-z0-9]+)*/g) ?? []).flatMap((t) => {
    const parts = t.split(/[-_]/);
    return parts.length > 1 ? [t, ...parts] : [t];
  }).map(stemToken);
}

const KIND_WEIGHT: Record<SearchKind, number> = { chapter: 1.3, term: 1.25, decision: 1.15, section: 1, exercise: 1, reference: 0.75 };

export class SearchIndex {
  private entries: Entry[] = [];
  private df = new Map<string, number>();
  private vocab: string[] = [];

  constructor(docs: SearchDoc[]) {
    for (const doc of docs) {
      const tf = new Map<string, number>();
      for (const t of tokenize(doc.text)) tf.set(t, (tf.get(t) ?? 0) + 1);
      const title = new Set(tokenize(doc.title));
      for (const t of new Set([...tf.keys(), ...title])) this.df.set(t, (this.df.get(t) ?? 0) + 1);
      this.entries.push({ doc, title, tf });
    }
    this.vocab = [...this.df.keys()];
  }

  get size() {
    return this.entries.length;
  }

  search(query: string, limit = 30): SearchHit[] {
    const raw = tokenize(query);
    if (!raw.length) return [];
    const endsWithSpace = /\s$/.test(query);
    // Expand the last term by prefix (bounded) unless the user finished typing it.
    const groups: string[][] = raw.map((t, i) => {
      if (i < raw.length - 1 || endsWithSpace || t.length < 2) return [t];
      const ext = this.vocab.filter((v) => v.startsWith(t)).slice(0, 40);
      return ext.length ? [...new Set([t, ...ext])] : [t];
    });
    const N = this.entries.length;
    const phrase = query.trim().toLowerCase();
    const hits: SearchHit[] = [];

    for (const e of this.entries) {
      let score = 0;
      let all = true;
      for (const group of groups) {
        let best = 0;
        for (const t of group) {
          const idf = Math.log(1 + N / (1 + (this.df.get(t) ?? 0)));
          const exact = t === group[0] ? 1 : 0.7;
          const titleHit = e.title.has(t) ? 6 * exact : 0;
          const tf = e.tf.get(t) ?? 0;
          const bodyHit = tf ? (1 + Math.log(tf)) * idf * exact : 0;
          best = Math.max(best, titleHit + bodyHit);
        }
        if (best === 0) {
          all = false;
          break;
        }
        score += best;
      }
      if (!all) continue;
      const titleLower = e.doc.title.toLowerCase();
      if (titleLower === phrase) score += 25;
      else if (titleLower.includes(phrase)) score += 10;
      else if (e.doc.text.toLowerCase().includes(phrase)) score += 3;
      hits.push({ doc: e.doc, score: score * KIND_WEIGHT[e.doc.kind], snippet: makeSnippet(e.doc.text, groups.flat()) });
    }
    return hits.sort((a, b) => b.score - a.score).slice(0, limit);
  }
}

/** A ~160 char window around the first hit, with match ranges for highlighting. */
export function makeSnippet(text: string, terms: string[], width = 160): SearchHit["snippet"] {
  const lower = text.toLowerCase();
  const needles = [...new Set(terms)].filter((t) => t.length > 1).sort((a, b) => b.length - a.length);
  let first = -1;
  for (const n of needles) {
    const i = lower.indexOf(n);
    if (i >= 0 && (first < 0 || i < first)) first = i;
  }
  const start = Math.max(0, first < 0 ? 0 : first - 50);
  let snippet = text.slice(start, start + width);
  const prefix = start > 0 ? "…" : "";
  const suffix = start + width < text.length ? "…" : "";
  snippet = prefix + snippet + suffix;
  const marks: [number, number][] = [];
  const sl = snippet.toLowerCase();
  for (const n of needles) {
    let i = sl.indexOf(n);
    while (i >= 0) {
      if (!marks.some(([a, b]) => i < b && i + n.length > a)) marks.push([i, i + n.length]);
      i = sl.indexOf(n, i + n.length);
    }
  }
  return { text: snippet, marks: marks.sort((a, b) => a[0] - b[0]) };
}

export function buildSearchDocs(hb: Handbook): SearchDoc[] {
  const docs: SearchDoc[] = [];
  for (const c of hb.chapters) {
    const ctx = `Chapter ${c.number}`;
    docs.push({ id: `ch-${c.number}`, kind: "chapter", title: c.title, context: ctx, text: `${c.title}. ${c.problem} ${c.objectives.join(" ")}`, href: `/handbook/${c.slug}` });
    for (const s of c.sections) {
      if (/^references$/i.test(s.title)) continue;
      docs.push({
        id: `sec-${c.number}-${s.id}`,
        kind: "section",
        title: s.number ? `${s.number} ${s.title}` : s.title,
        context: `${ctx} — ${c.title}`,
        text: `${s.title}. ${s.text}`,
        href: `/handbook/${c.slug}#${s.id}`,
      });
    }
  }
  for (const t of hb.glossary) {
    docs.push({ id: `term-${t.slug}`, kind: "term", title: t.term, context: "Glossary", text: `${t.term}. ${toPlainText(t.definition)}`, href: `/glossary#${t.slug}` });
  }
  for (const a of hb.adrs) {
    const decision = a.sections.find((s) => s.kind === "decision");
    docs.push({ id: a.id, kind: "decision", title: `${a.id}: ${a.title}`, context: `Decision — ${a.status}`, text: `${a.title}. ${toPlainText(decision?.markdown ?? "")}`, href: `/decisions/${a.id}` });
    for (const s of a.sections) {
      if (s.kind === "references" || s.kind === "status") continue;
      docs.push({ id: `${a.id}-${s.id}`, kind: "section", title: s.title, context: `${a.id}: ${a.title}`, text: toPlainText(s.markdown), href: `/decisions/${a.id}#${s.id}` });
    }
  }
  for (const x of hb.exercises) {
    docs.push({ id: `ex-${x.file}`, kind: "exercise", title: x.file, context: x.chapter ? `Exercise — Chapter ${x.chapter}` : "Exercise", text: `${x.file} ${x.docstring}`, href: `/exercises#${x.file.replace(/\.py$/, "")}` });
  }
  for (const r of hb.references.values()) {
    docs.push({ id: `ref-${r.id}`, kind: "reference", title: `${r.id} ${r.citation.replace(/https?:\/\/\S+/g, "").slice(0, 110)}`, context: "Reference", text: r.citation, href: `/references#${r.id}` });
  }
  return docs;
}
