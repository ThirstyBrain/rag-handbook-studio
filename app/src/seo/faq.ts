import { splitByHeadings, toPlainText } from "@/content/parse/text";
import { stripEvidence } from "./text";

export interface FaqItem {
  question: string;
  answer: string;
}

const ITEM = /^\d+\.\s+\*\*(.+?)\*\*\s*(.*)$/;
const ANSWER = /\*Model answer:\*\s*(.*?)(?=\s\*(?:Follow-up|Common wrong answer|Wrong answer|Common mistake)[^*]*\*|$)/is;

/**
 * Question and model-answer pairs from a chapter's "Interview Questions" section, for FAQPage
 * markup. Items without a written model answer are skipped rather than invented.
 */
export function parseInterviewFaq(chapterMarkdown: string): FaqItem[] {
  const body = splitByHeadings(chapterMarkdown, 2).find((b) => b.heading && /Interview Questions/i.test(b.heading.text))?.body;
  if (!body) return [];
  const items: FaqItem[] = [];
  for (const line of body.split(/\r?\n/)) {
    const m = ITEM.exec(line.trim());
    if (!m) continue;
    const answer = ANSWER.exec(m[2]!)?.[1];
    if (!answer) continue;
    const text = stripEvidence(toPlainText(answer));
    if (text) items.push({ question: stripEvidence(toPlainText(m[1]!)), answer: text });
  }
  return items;
}
