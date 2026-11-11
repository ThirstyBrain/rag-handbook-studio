import type { Adr, AdrSection, AdrSectionKind } from "../types";
import { slugify, splitByHeadings } from "./text";

const KIND_RULES: [RegExp, AdrSectionKind][] = [
  [/^status/i, "status"],
  [/^context/i, "context"],
  [/^requirements/i, "requirements"],
  [/^options/i, "options"],
  [/^decision/i, "decision"],
  [/^rationale/i, "rationale"],
  [/^trade-?offs/i, "tradeoffs"],
  [/^consequences/i, "consequences"],
  [/^security/i, "security"],
  [/^performance/i, "performance"],
  [/^amendment/i, "amendment"],
  [/^verification/i, "verification"],
  [/^evidence gap/i, "gaps"],
  [/^reversal/i, "reversal"],
  [/^references/i, "references"],
];

export function adrSectionKind(title: string): AdrSectionKind {
  return KIND_RULES.find(([re]) => re.test(title))?.[1] ?? "other";
}

export function parseAdr(sourcePath: string, markdown: string): Adr {
  const fileName = sourcePath.split("/").pop() ?? sourcePath;
  const slug = fileName.replace(/\.md$/, "");
  const number = Number(/ADR-(\d+)/.exec(fileName)?.[1] ?? 0);
  const id = `ADR-${String(number).padStart(3, "0")}`;
  const blocks = splitByHeadings(markdown, 2);
  const h1 = blocks.find((b) => b.heading?.level === 1)?.heading?.text ?? slug;
  const title = h1.replace(/^ADR-\d+:\s*/, "");

  const sections: AdrSection[] = blocks
    .filter((b) => b.heading?.level === 2)
    .map((b) => ({ id: slugify(b.heading!.text), title: b.heading!.text, kind: adrSectionKind(b.heading!.text), markdown: b.body.trim() }));

  const statusLine = sections.find((s) => s.kind === "status")?.markdown.split(/\n/)[0]?.trim() ?? "";
  const status = /^([A-Za-z]+)/.exec(statusLine)?.[1] ?? "Unknown";

  return { id, number, slug, title, status, statusLine, sourcePath, sections, chapters: [] };
}
