import { execFileSync } from "node:child_process";

export interface ContentDates {
  published: string;
  modified: string;
}

/**
 * First and last commit dates for each handbook source file, read from git history once per build.
 * Keys are paths relative to the handbook folder ("docs/chapters/01-....md"). If git is unavailable
 * (for example a source archive), the result is empty and pages simply omit dates rather than invent them.
 */
export function readContentDates(handbookDir: string): Record<string, ContentDates> {
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
  // Newest commit first: the first sighting of a file is its last change, the final one its first.
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
