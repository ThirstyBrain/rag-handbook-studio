/** Small, pure text helpers shared by the parsers. No DOM, no Markdown library. */

export function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/<[^>]+>/g, "")
    .replace(/[`*_~[\]()]/g, "")
    .replace(/&[a-z]+;/g, "")
    .replace(/[^\p{L}\p{N}\s.-]/gu, "")
    .trim()
    .replace(/[\s.]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

/** Strip Markdown syntax well enough for search snippets and previews. */
export function toPlainText(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*\n]+)\*/g, "$1")
    .replace(/^\s*>\s?/gm, "")
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+\.\s+/gm, "")
    .replace(/^\|?[\s:-]+\|[\s|:-]*$/gm, " ")
    .replace(/\|/g, " ")
    .replace(/^#+\s+/gm, "")
    .replace(/\s+/g, " ")
    .trim();
}

export interface Block {
  heading: { level: number; text: string } | null;
  body: string;
}

/**
 * Split Markdown into blocks at headings of `maxLevel` or shallower, ignoring "#" lines inside
 * fenced code. The first block holds content before the first heading.
 */
export function splitByHeadings(md: string, maxLevel = 3): Block[] {
  const blocks: Block[] = [{ heading: null, body: "" }];
  let inFence = false;
  for (const line of md.split(/\r?\n/)) {
    if (/^\s*(```|~~~)/.test(line)) inFence = !inFence;
    const m = !inFence ? /^(#{1,6})\s+(.*)$/.exec(line) : null;
    if (m && m[1]!.length <= maxLevel) {
      blocks.push({ heading: { level: m[1]!.length, text: m[2]!.trim() }, body: "" });
      continue;
    }
    const last = blocks[blocks.length - 1]!;
    last.body += line + "\n";
  }
  return blocks;
}

export function firstParagraph(md: string): string {
  const para = md
    .trim()
    .split(/\n\s*\n/)
    .find((p) => p.trim() && !p.trim().startsWith("```") && !p.trim().startsWith("|"));
  return para ? toPlainText(para) : "";
}

export function wordCount(md: string): number {
  return toPlainText(md).split(/\s+/).filter(Boolean).length;
}

/** "Chapter 9 — Hybrid Search" -> { number: 9, title: "Hybrid Search" } */
export function parseChapterHeading(line: string): { number: number; title: string } | null {
  const m = /^#\s*Chapter\s+(\d+)\s*[—–-]\s*(.+)$/.exec(line.trim());
  return m ? { number: Number(m[1]), title: m[2]!.trim() } : null;
}

/** "9.4.1 BM25" -> { number: "9.4.1", title: "BM25" } */
export function splitSectionNumber(text: string): { number: string; title: string } {
  const m = /^(\d+(?:\.\d+)*)\.?\s+(.*)$/.exec(text);
  return m ? { number: m[1]!, title: m[2]! } : { number: "", title: text };
}

export function unique<T>(items: Iterable<T>): T[] {
  return [...new Set(items)];
}

/** First sentence of a plain-text paragraph (used for standfirsts and one-line descriptions). */
export function firstSentence(text: string): string {
  const m = /^(.+?[.!?])(\s+[A-Z(]|$)/.exec(text);
  return m ? m[1]! : text;
}
