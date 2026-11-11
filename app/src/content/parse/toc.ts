import type { ChapterEntry, ChapterStatus, PartInfo } from "../types";

const STATUSES: ChapterStatus[] = ["complete", "in-progress", "pending", "researching", "drafting", "review"];

/** Parses project-management/MASTER-TOC.md: "## Part I — Title (M2)" headings followed by chapter tables. */
export function parseMasterToc(md: string): { parts: PartInfo[]; entries: ChapterEntry[] } {
  const parts: PartInfo[] = [];
  const entries: ChapterEntry[] = [];
  let current: PartInfo | null = null;

  for (const line of md.split(/\r?\n/)) {
    const part = /^##\s+Part\s+([IVXLC]+)\s*[—–-]\s*(.+?)\s*(?:\(([^)]+)\))?\s*$/.exec(line);
    if (part) {
      current = { id: `part-${part[1]!.toLowerCase()}`, roman: part[1]!, title: part[2]!.trim(), milestone: part[3] ?? "" };
      parts.push(current);
      continue;
    }
    if (line.startsWith("## ")) {
      current = null;
      continue;
    }
    if (!current) continue;
    const row = /^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*[^|]*\|\s*([^|]+?)\s*\|\s*$/.exec(line);
    if (!row) continue;
    const statusText = row[3]!;
    const normalised = statusText.toLowerCase().replace(/\s+/g, "-");
    const status = STATUSES.find((s) => normalised.startsWith(s)) ?? "pending";
    const note = /\(([^)]*)\)/.exec(statusText)?.[1] ?? "";
    entries.push({ number: Number(row[1]), title: row[2]!, partId: current.id, status, statusNote: note });
  }
  return { parts, entries };
}
