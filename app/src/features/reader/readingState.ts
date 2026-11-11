import { readJson, writeJson } from "@/shared/storage/storage";

/** Per-viewer reading state kept in localStorage. Never required for the page to work. */
const COMPLETED = "completed-chapters";
const LAST_READ = "last-read";

export function getCompleted(): Set<number> {
  return new Set(readJson<number[]>(COMPLETED, []));
}

export function markCompleted(n: number): boolean {
  const s = getCompleted();
  if (s.has(n)) return false;
  s.add(n);
  writeJson(COMPLETED, [...s].sort((a, b) => a - b));
  return true;
}

export interface LastRead {
  slug: string;
  sectionId: string | null;
}

/** Where "Continue reading" should take the reader: the last chapter and section they were in. */
export function getLastRead(): LastRead | null {
  return readJson<LastRead | null>(LAST_READ, null);
}

export function setLastRead(value: LastRead): void {
  writeJson(LAST_READ, value);
}
