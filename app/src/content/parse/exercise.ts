import type { Exercise, ExerciseRun } from "../types";

export function parseExercise(file: string, source: string, runs: ExerciseRun[]): Exercise {
  const doc = /^(?:#!.*\n)?\s*"""([\s\S]*?)"""/.exec(source)?.[1]?.trim() ?? "";
  const title = doc.split(/\n/)[0]?.replace(/\.$/, "") ?? file;
  // Local helper modules are single-underscore names such as `_toy_ir`; `__future__` is not one.
  const helpers = [...source.matchAll(/^from\s+(_(?!_)[a-z0-9_]+)\s+import/gm)].map((m) => `${m[1]}.py`);
  const chapter = /^ch(\d+)_/.exec(file)?.[1];
  return {
    file,
    chapter: chapter ? Number(chapter) : null,
    title,
    docstring: doc,
    source,
    helpers: [...new Set(helpers)],
    runs: runs.filter((r) => r.file === file).sort((a, b) => a.args.localeCompare(b.args)),
  };
}
