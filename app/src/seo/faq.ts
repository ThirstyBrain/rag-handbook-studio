import { splitByHeadings, toPlainText } from "@/content/parse/text";
import { stripEvidence } from "./text";

export interface FaqItem {
  question: string;
  answer: string;
}

/** "1. **Question?** answer text..." */
const ITEM = /^\d+\.\s+\*\*(.+?)\*\*\s*(.*)$/;
/** Everything from the first follow-up or wrong-answer note onward is not part of the answer. */
const TAIL = /\s\*(?:Follow-up|Common wrong answer|Wrong answer|Common mistake)[^*]*\*[\s\S]*$/i;
const MIN_ANSWER_WORDS = 8;

/**
 * Question and answer pairs from a chapter's "Interview Questions" section, for FAQPage markup and the
 * interview hub. Chapters write answers either after a "*Model answer:*" label or directly after the
 * question. Items that only point elsewhere ("See §1.8.") are skipped rather than invented.
 */
export function parseInterviewFaq(chapterMarkdown: string): FaqItem[] {
  const body = splitByHeadings(chapterMarkdown, 2).find((b) => b.heading && /Interview Questions/i.test(b.heading.text))?.body;
  if (!body) return [];
  const items: FaqItem[] = [];
  for (const line of body.split(/\r?\n/)) {
    const m = ITEM.exec(line.trim());
    if (!m) continue;
    let answer = m[2]!.replace(TAIL, "");
    const labelled = /\*Model answer:\*\s*([\s\S]*)$/i.exec(answer);
    if (labelled) answer = labelled[1]!;
    // "*Short:* … *Deep:* …" labels are structure for the reader; the words stay.
    answer = answer.replace(/\*(?:Short|Deep|Answer):\*\s*/gi, "");
    const text = stripEvidence(toPlainText(answer));
    if (text.split(/\s+/).length < MIN_ANSWER_WORDS) continue;
    items.push({ question: stripEvidence(toPlainText(m[1]!)), answer: text });
  }
  return items;
}
