import { parseAdr } from "./parse/adr";
import { parseChapter } from "./parse/chapter";
import { parseExercise } from "./parse/exercise";
import { parseGlossary, parseReferences } from "./parse/glossary";
import { parseMasterToc } from "./parse/toc";
import * as src from "./source";
import type { Adr, Chapter, ChapterEntry, Diagram, Exercise, GlossaryTerm, PartInfo, Reference } from "./types";

/** The assembled, read-only handbook model. Built once, on first access. */
export interface Handbook {
  parts: PartInfo[];
  /** Every chapter in MASTER-TOC order, written or planned. */
  entries: ChapterEntry[];
  /** Written chapters, by number. */
  chapters: Chapter[];
  adrs: Adr[];
  glossary: GlossaryTerm[];
  references: Map<string, Reference>;
  exercises: Exercise[];
  diagrams: Map<string, Diagram>;
}

let cached: Handbook | null = null;

export function getHandbook(): Handbook {
  if (cached) return cached;
  const { parts, entries } = parseMasterToc(src.masterTocMd);
  const entryByNumber = new Map(entries.map((e) => [e.number, e]));

  const chapters = Object.entries(src.chapterFiles)
    .map(([key, md]) => {
      const number = Number(src.fileName(key).slice(0, 2));
      return parseChapter(src.repoPath(key), md, entryByNumber.get(number));
    })
    .sort((a, b) => a.number - b.number);

  // Chapters that exist on disk but are missing from MASTER-TOC still appear (as complete).
  for (const c of chapters) {
    if (!entryByNumber.has(c.number)) entries.push({ number: c.number, title: c.title, partId: c.partId, status: c.status, statusNote: "" });
  }
  entries.sort((a, b) => a.number - b.number);

  const adrs = Object.entries(src.adrFiles)
    .map(([key, md]) => parseAdr(src.repoPath(key), md))
    .sort((a, b) => a.number - b.number);
  for (const adr of adrs) adr.chapters = chapters.filter((c) => c.adrs.includes(adr.id)).map((c) => c.number);

  const diagrams = new Map<string, Diagram>();
  for (const [key, source] of Object.entries(src.diagramFiles)) {
    const file = src.fileName(key);
    diagrams.set(file, { file, chapter: Number(file.slice(0, 2)), source });
  }

  const exerciseSources = new Map(Object.entries(src.exerciseFiles).map(([k, v]) => [src.fileName(k), v]));
  const exercises = [...exerciseSources.entries()]
    .filter(([file]) => /^ch\d+_/.test(file))
    .map(([file, source]) => parseExercise(file, source, src.capturedRuns))
    .sort((a, b) => a.file.localeCompare(b.file));

  cached = {
    parts,
    entries,
    chapters,
    adrs,
    glossary: parseGlossary(src.glossaryMd),
    references: parseReferences(src.referencesMd, chapters.map((c) => c.markdown)),
    exercises,
    diagrams,
  };
  return cached;
}

/** Raw source of a helper module such as `_toy_ir.py`. */
export function getExerciseHelper(file: string): string | undefined {
  const key = Object.keys(src.exerciseFiles).find((k) => src.fileName(k) === file);
  return key ? src.exerciseFiles[key] : undefined;
}

export const findChapter = (slugOrNumber: string | number): Chapter | undefined =>
  getHandbook().chapters.find((c) => c.slug === slugOrNumber || c.number === Number(slugOrNumber));

export const findAdr = (id: string): Adr | undefined => getHandbook().adrs.find((a) => a.id.toLowerCase() === id.toLowerCase() || a.slug === id);

export const findExercise = (file: string): Exercise | undefined => getHandbook().exercises.find((e) => e.file === file);

export function chapterHref(c: Pick<Chapter, "slug">, sectionId?: string): string {
  return `/handbook/${c.slug}${sectionId ? `#${sectionId}` : ""}`;
}

export function chapterHrefByNumber(n: number, sectionId?: string): string | null {
  const c = findChapter(n);
  return c ? chapterHref(c, sectionId) : null;
}
