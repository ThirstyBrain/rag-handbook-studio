/** Domain model of the handbook as the UI sees it. Every value is derived from the source repository. */

export type EvidenceKind = "S" | "E" | "A" | "I" | "X" | "V" | "N";

export interface Section {
  /** DOM id, stable across renders: slug of the heading text. */
  id: string;
  level: 2 | 3;
  /** Section number as written in the heading, e.g. "9.4.1" (empty when unnumbered). */
  number: string;
  title: string;
  /** Plain text of the section body (for search and previews). */
  text: string;
}

export interface PartInfo {
  id: string;
  roman: string;
  title: string;
  milestone: string;
}

export type ChapterStatus = "complete" | "in-progress" | "pending" | "researching" | "drafting" | "review";

export interface ChapterEntry {
  number: number;
  title: string;
  partId: string;
  status: ChapterStatus;
  /** Status note from MASTER-TOC, e.g. "with recorded limitations OI-010". */
  statusNote: string;
}

export interface Chapter extends ChapterEntry {
  slug: string;
  sourcePath: string;
  markdown: string;
  sections: Section[];
  objectives: string[];
  /** Knowledge-checkpoint questions (Markdown of each top-level list item), in source order. */
  checkpoint: string[];
  /** Id of the checkpoint section, for linking back into the chapter. */
  checkpointSectionId: string | null;
  /** First paragraph of the "Problem Statement" section. */
  problem: string;
  /** Body of the "Summary" section. */
  summary: string;
  wordCount: number;
  readingMinutes: number;
  /** Diagram sources referenced by the chapter (file names under docs/assets/diagrams). */
  diagrams: string[];
  /** Exercise scripts referenced by the chapter. */
  exercises: string[];
  /** ADR ids referenced by the chapter, e.g. "ADR-004". */
  adrs: string[];
  /** Evidence marker counts, e.g. { X: 12, E: 30, S: 44 }. */
  evidence: Partial<Record<EvidenceKind, number>>;
}

export interface AdrSection {
  id: string;
  title: string;
  /** Normalised kind, used for the decision-anatomy navigation. */
  kind: AdrSectionKind;
  markdown: string;
}

export type AdrSectionKind =
  | "status"
  | "context"
  | "requirements"
  | "options"
  | "decision"
  | "rationale"
  | "tradeoffs"
  | "consequences"
  | "security"
  | "performance"
  | "amendment"
  | "verification"
  | "gaps"
  | "reversal"
  | "references"
  | "other";

export interface Adr {
  id: string; // "ADR-004"
  number: number;
  slug: string;
  title: string;
  /** First word of the status section: Proposed / Accepted / ... */
  status: string;
  statusLine: string;
  sourcePath: string;
  sections: AdrSection[];
  /** Chapters that reference this ADR. */
  chapters: number[];
}

export interface GlossaryTerm {
  term: string;
  slug: string;
  /** Definition text without the trailing chapter note. */
  definition: string;
  chapters: number[];
}

export interface Reference {
  id: string; // "S67"
  citation: string;
  url?: string;
  /** Review status recorded by the handbook (read / abstract / partial ...). */
  status?: string;
}

export interface ExerciseRun {
  file: string;
  args: string;
  sha256: string;
  exitCode: number;
  durationMs: number;
  stdout: string;
  stderr: string;
  python: string;
  capturedAt: string;
}

export interface Exercise {
  file: string;
  chapter: number | null;
  /** First line of the module docstring. */
  title: string;
  docstring: string;
  source: string;
  /** Helper modules the script imports from the exercises folder. */
  helpers: string[];
  runs: ExerciseRun[];
}

export interface Diagram {
  file: string;
  chapter: number;
  source: string;
}
