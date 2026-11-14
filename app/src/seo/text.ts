import { EVIDENCE_TAG } from "@/content/parse/evidence";
import type { Chapter } from "@/content/types";

/** Removes evidence tags such as [S22, E] so prose reads cleanly outside the handbook UI. */
export function stripEvidence(text: string): string {
  return text.replace(new RegExp(EVIDENCE_TAG.source, "g"), "").replace(/\s+([.,;:])/g, "$1").replace(/\s+/g, " ").trim();
}

/** Cuts at a sentence end when one fits, otherwise at a word boundary with an ellipsis. */
export function truncate(text: string, max: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const window = clean.slice(0, max);
  const sentenceEnd = Math.max(window.lastIndexOf(". "), window.lastIndexOf("? "), window.lastIndexOf("! "));
  if (sentenceEnd > max * 0.6) return window.slice(0, sentenceEnd + 1);
  const wordEnd = window.lastIndexOf(" ");
  return `${window.slice(0, wordEnd > 0 ? wordEnd : max).replace(/[,;:(\s]+$/, "")}…`;
}

const sentences = (text: string): string[] => text.match(/[^.!?]+[.!?]+(?=\s|$)/g)?.map((s) => s.trim()) ?? [text];
const words = (text: string): string[] => text.split(/\s+/).filter(Boolean);

const TLDR_MIN_WORDS = 40;
const TLDR_MAX_WORDS = 60;

/**
 * A direct answer for the top of a chapter, built from the chapter's own Summary: whole sentences
 * until it reaches 40 words, never more than 60. Answer engines lift this kind of block verbatim.
 */
export function chapterTldr(chapter: Pick<Chapter, "summary" | "problem">): string {
  const source = stripEvidence(chapter.summary || chapter.problem);
  if (!source) return "";
  let out = "";
  for (const s of sentences(source)) {
    const next = out ? `${out} ${s}` : s;
    if (words(next).length > TLDR_MAX_WORDS) {
      if (!out) return `${words(s).slice(0, TLDR_MAX_WORDS).join(" ").replace(/[,;:(]+$/, "")}…`;
      break;
    }
    out = next;
    if (words(out).length >= TLDR_MIN_WORDS) break;
  }
  return out;
}

/** One-sentence description for <meta name="description">. */
export function chapterDescription(chapter: Pick<Chapter, "problem" | "summary" | "objectives" | "title" | "number">, max: number): string {
  // Living chapters may lack a Problem Statement or Summary; fall back to what the reader will learn.
  const text = chapter.problem || chapter.summary || chapter.objectives.slice(0, 2).join(" ") || `Chapter ${chapter.number}: ${chapter.title}.`;
  return truncate(stripEvidence(text), max);
}
