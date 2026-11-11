import { marked, type Tokens } from "marked";
import type { Chapter, ChapterEntry, Section } from "../types";
import { countEvidence } from "./evidence";
import { firstParagraph, parseChapterHeading, slugify, splitByHeadings, splitSectionNumber, toPlainText, unique, wordCount } from "./text";

const WORDS_PER_MINUTE = 220;

export function parseChapter(sourcePath: string, markdown: string, entry?: ChapterEntry): Chapter {
  const fileName = sourcePath.split("/").pop() ?? sourcePath;
  const slug = fileName.replace(/\.md$/, "");
  const firstLine = markdown.split(/\r?\n/, 1)[0] ?? "";
  const heading = parseChapterHeading(firstLine);
  const number = heading?.number ?? Number(slug.slice(0, 2));
  const title = heading?.title ?? entry?.title ?? slug;

  const blocks = splitByHeadings(markdown, 3);
  const sections: Section[] = [];
  const seen = new Map<string, number>();
  for (const b of blocks) {
    if (!b.heading || b.heading.level < 2) continue;
    const { number: secNumber, title: secTitle } = splitSectionNumber(b.heading.text);
    let id = slugify(b.heading.text);
    const n = seen.get(id) ?? 0;
    seen.set(id, n + 1);
    if (n > 0) id = `${id}-${n}`;
    sections.push({ id, level: b.heading.level as 2 | 3, number: secNumber, title: secTitle, text: toPlainText(b.body) });
  }

  const bodyOf = (pattern: RegExp) => blocks.find((b) => b.heading && b.heading.level === 2 && pattern.test(b.heading.text))?.body ?? "";

  const objectives = [...bodyOf(/Learning Objectives/i).matchAll(/^\s*\d+\.\s+(.+)$/gm)].map((m) => toPlainText(m[1]!));

  // "N.16 Knowledge Checkpoint / Exercises" (or a plain "N.8 Exercises") holds the chapter's questions.
  const checkpointRe = /Knowledge Checkpoint|^\d+\.\d+\s+Exercises\s*$/i;
  const checkpointBody = bodyOf(checkpointRe);
  const checkpoint = marked
    .lexer(checkpointBody)
    .filter((t): t is Tokens.List => t.type === "list")
    .flatMap((l) => l.items.map((it) => it.text.trim()))
    .filter(Boolean);
  const checkpointSectionId = sections.find((s) => s.level === 2 && checkpointRe.test(`${s.number} ${s.title}`.trim()))?.id ?? null;
  const words = wordCount(markdown);

  return {
    number,
    title,
    partId: entry?.partId ?? "",
    status: entry?.status ?? "complete",
    statusNote: entry?.statusNote ?? "",
    slug,
    sourcePath,
    markdown,
    sections,
    objectives,
    checkpoint,
    checkpointSectionId,
    problem: firstParagraph(bodyOf(/Problem Statement/i)),
    summary: toPlainText(bodyOf(/^\d+\.\d+\s+Summary/i)),
    wordCount: words,
    readingMinutes: Math.max(1, Math.round(words / WORDS_PER_MINUTE)),
    diagrams: unique([...markdown.matchAll(/diagrams\/([\w.-]+\.mmd)/g)].map((m) => m[1]!)),
    exercises: unique([...markdown.matchAll(/(ch\d+_[a-z0-9_]+\.py)/g)].map((m) => m[1]!)),
    adrs: unique([...markdown.matchAll(/ADR-(\d{3})/g)].map((m) => `ADR-${m[1]}`)).sort(),
    evidence: countEvidence(markdown),
  };
}
