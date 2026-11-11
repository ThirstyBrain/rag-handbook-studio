/**
 * The ONLY module that knows where handbook files live. Everything is read at build time through
 * Vite's glob imports from the read-only `@handbook` alias (see vite.config.ts), so the handbook
 * stays the single source of truth: edit a chapter there and the app picks it up on reload.
 */
import exerciseRuns from "@/generated/exercise-runs.json";
import type { ExerciseRun } from "./types";

export const chapterFiles = import.meta.glob<string>("@handbook/docs/chapters/*.md", { query: "?raw", import: "default", eager: true });
export const adrFiles = import.meta.glob<string>("@handbook/adr/ADR-*.md", { query: "?raw", import: "default", eager: true });
export const diagramFiles = import.meta.glob<string>("@handbook/docs/assets/diagrams/*.mmd", { query: "?raw", import: "default", eager: true });
export const exerciseFiles = import.meta.glob<string>("@handbook/docs/exercises/*.py", { query: "?raw", import: "default", eager: true });

export { default as glossaryMd } from "@handbook/docs/11-Glossary.md?raw";
export { default as referencesMd } from "@handbook/docs/12-References.md?raw";
export { default as masterTocMd } from "@handbook/project-management/MASTER-TOC.md?raw";

export const capturedRuns: ExerciseRun[] = (exerciseRuns as { runs: ExerciseRun[] }).runs;

/** Repository-relative path for display, e.g. "docs/chapters/09-hybrid-search.md". */
export function repoPath(globKey: string): string {
  const i = globKey.search(/\/(docs|adr|project-management)\//);
  return i >= 0 ? globKey.slice(i + 1) : globKey;
}

export function fileName(globKey: string): string {
  return globKey.split("/").pop() ?? globKey;
}
