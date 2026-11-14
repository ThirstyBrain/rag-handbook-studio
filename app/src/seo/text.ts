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

/** Splits only where a sentence ends and a new one starts with a capital, so "§1.4.5" and "2(b)" stay intact. */
const sentences = (text: string): string[] => text.split(/(?<=[.!?])\s+(?=[A-Z"“(])/).map((s) => s.trim()).filter(Boolean);
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

const DESCRIPTION_MIN = 140;

/**
 * A meta description of 140-155 characters: whole sentences from `text` while they fit, then the first
 * fillers that fit if the result is still short. A single over-long first sentence is cut at a word.
 */
export function composeDescription(text: string, fillers: string[], max: number): string {
  const clean = stripEvidence(text);
  let out = "";
  for (const s of sentences(clean)) {
    const next = out ? `${out} ${s}` : s;
    if (next.length > max) break;
    out = next;
  }
  if (!out) out = truncate(clean, max);
  for (const filler of fillers) {
    if (out.length >= DESCRIPTION_MIN) break;
    if (`${out} ${filler}`.length <= max) out = `${out} ${filler}`;
  }
  return out;
}

/** Title of at most `max` characters: with the site suffix when it fits, without it otherwise, cut at a word as a last resort. */
export function fitTitle(main: string, suffix: string, max: number): string {
  if (main.length + suffix.length <= max) return main + suffix;
  if (main.length <= max) return main;
  return truncate(main, max);
}

export function chapterDescription(chapter: Pick<Chapter, "problem" | "summary" | "objectives" | "title" | "number">, max: number): string {
  // Living chapters may lack a Problem Statement or Summary; fall back to what the reader will learn.
  // The Summary states the chapter's conclusion, which makes the better answer-shaped description.
  const text = chapter.summary || chapter.problem || chapter.objectives.slice(0, 2).join(" ") || `${chapter.title}.`;
  return composeDescription(text, [`Chapter ${chapter.number} of the RAG Architecture Handbook.`, "Evidence-labelled, with runnable exercises.", "Production RAG.", "Free to read."], max);
}
