import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export interface ContentDates {
  published: string;
  modified: string;
}

interface BaselineEntry extends ContentDates {
  sha256: string;
}

/** Handbook sources that get dates, relative to the handbook folder. */
const SOURCE_DIRS: { dir: string; pattern: RegExp }[] = [
  { dir: "docs/chapters", pattern: /\.md$/ },
  { dir: "adr", pattern: /^ADR-.*\.md$/ },
];

/** Line endings differ between Windows checkouts and CI, so hash a normalised form. */
export const hashContent = (text: string): string => createHash("sha256").update(text.replace(/\r\n/g, "\n")).digest("hex");

function listSources(handbookDir: string): string[] {
  return SOURCE_DIRS.flatMap(({ dir, pattern }) => {
    const abs = path.join(handbookDir, dir);
    return fs.existsSync(abs) ? fs.readdirSync(abs).filter((f) => pattern.test(f)).map((f) => `${dir}/${f}`) : [];
  });
}

/** First and last commit date per file, newest commit first. Empty when git is unavailable (e.g. a source archive). */
function readGitDates(handbookDir: string): Record<string, ContentDates> {
  let log: string;
  try {
    log = execFileSync("git", ["-C", handbookDir, "log", "--no-renames", "--relative", "--format=@%cI", "--name-only", "--", "docs/chapters", "adr"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      maxBuffer: 32 * 1024 * 1024,
    });
  } catch {
    return {};
  }
  const dates: Record<string, ContentDates> = {};
  let current = "";
  for (const line of log.split(/\r?\n/)) {
    if (line.startsWith("@")) current = line.slice(1);
    else if (line.trim() && current) {
      const entry = dates[line];
      if (entry) entry.published = current;
      else dates[line] = { published: current, modified: current };
    }
  }
  return dates;
}

function readBaseline(file: string): Record<string, BaselineEntry> {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8")) as Record<string, BaselineEntry>;
  } catch {
    return {};
  }
}

/**
 * Publication and last-modified dates per handbook source file.
 *
 * `content-dates.json` records the real authoring dates together with a hash of the content they
 * describe (see scripts/record-content-dates.mjs). While a file still matches its recorded hash those
 * dates are used. Once the content changes, its last git commit date takes over, so dates move only
 * when the text does. With neither source a file simply has no date; nothing is invented.
 */
export function readContentDates(handbookDir: string, baselineFile: string): Record<string, ContentDates> {
  const baseline = readBaseline(baselineFile);
  const git = readGitDates(handbookDir);
  const result: Record<string, ContentDates> = {};
  for (const key of listSources(handbookDir)) {
    const recorded = baseline[key];
    const hash = hashContent(fs.readFileSync(path.join(handbookDir, key), "utf8"));
    if (recorded && recorded.sha256 === hash) result[key] = { published: recorded.published, modified: recorded.modified };
    else if (git[key]) result[key] = { published: recorded?.published ?? git[key]!.published, modified: git[key]!.modified };
    else if (recorded) result[key] = { published: recorded.published, modified: recorded.modified };
  }
  return result;
}
