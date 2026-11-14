import { getHandbook } from "@/content/handbook";
import type { Chapter } from "@/content/types";
import { parseInterviewFaq, type FaqItem } from "@/seo/faq";

export interface InterviewGroup {
  chapter: Chapter;
  items: FaqItem[];
}

/** Interview questions with model answers, grouped by the chapter they come from. Chapters without any are left out. */
export function interviewGroups(): InterviewGroup[] {
  return getHandbook()
    .chapters.map((chapter) => ({ chapter, items: parseInterviewFaq(chapter.markdown) }))
    .filter((g) => g.items.length > 0);
}
