#!/usr/bin/env node
/**
 * Runs every handbook exercise (and every command-line variant a chapter cites, e.g. `--mutants`)
 * and records the REAL output in src/generated/exercise-runs.json.
 *
 * The handbook is read-only: scripts run with -I (isolated) and -B (no __pycache__ written).
 * If no Python interpreter is found, the previous capture is kept and the script exits 0,
 * so the app still builds — the UI shows the capture date so stale output is visible.
 *
 * Usage: node scripts/capture-exercises.mjs [filter]
 */
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const handbook = path.resolve(root, "../handbook");
const exercisesDir = path.join(handbook, "docs/exercises");
const chaptersDir = path.join(handbook, "docs/chapters");
const outFile = path.join(root, "src/generated/exercise-runs.json");
const filter = process.argv[2] ?? "";
const TIMEOUT_MS = 120_000;

function log(level, message, extra = {}) {
  console[level === "error" ? "error" : "log"](JSON.stringify({ level, scope: "capture-exercises", message, ...extra }));
}

function findPython() {
  const candidates = [process.env.PYTHON, "py", "python3", "python"].filter(Boolean);
  for (const cmd of candidates) {
    const r = spawnSync(cmd, ["--version"], { encoding: "utf8" });
    if (r.status === 0) return { cmd, version: (r.stdout || r.stderr).trim() };
  }
  return null;
}

/** Variants a chapter actually cites, e.g. "ch12_reranking.py --mutants". */
function citedVariants() {
  const variants = new Map();
  for (const f of fs.readdirSync(chaptersDir).filter((x) => x.endsWith(".md"))) {
    const text = fs.readFileSync(path.join(chaptersDir, f), "utf8");
    for (const m of text.matchAll(/(ch\d+_[a-z0-9_]+\.py)((?:\s+--[a-z-]+)+)/g)) {
      const args = m[2].trim().split(/\s+/);
      const set = variants.get(m[1]) ?? new Set();
      set.add(args.join(" "));
      variants.set(m[1], set);
    }
  }
  return variants;
}

function main() {
  const previous = fs.existsSync(outFile) ? JSON.parse(fs.readFileSync(outFile, "utf8")) : { runs: [] };
  const python = findPython();
  if (!python) {
    log("warn", "No Python interpreter found; keeping previous captures.", { kept: previous.runs.length });
    return;
  }
  const variants = citedVariants();
  const files = fs.readdirSync(exercisesDir).filter((f) => /^ch\d+_.+\.py$/.test(f) && f.includes(filter)).sort();
  const runs = filter ? previous.runs.filter((r) => !r.file.includes(filter)) : [];

  for (const file of files) {
    const source = fs.readFileSync(path.join(exercisesDir, file), "utf8");
    const sha256 = createHash("sha256").update(source).digest("hex");
    const argSets = ["", ...(variants.get(file) ?? [])];
    for (const args of argSets) {
      const started = Date.now();
      const r = spawnSync(python.cmd, ["-I", "-B", file, ...(args ? args.split(" ") : [])], {
        cwd: exercisesDir,
        encoding: "utf8",
        timeout: TIMEOUT_MS,
        env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1", PYTHONIOENCODING: "utf-8" },
      });
      const run = {
        file,
        args,
        sha256,
        exitCode: r.status ?? -1,
        durationMs: Date.now() - started,
        stdout: (r.stdout ?? "").replace(/\r\n/g, "\n"),
        stderr: (r.stderr ?? "").replace(/\r\n/g, "\n"),
        python: python.version,
        capturedAt: new Date().toISOString(),
      };
      runs.push(run);
      log(run.exitCode === 0 ? "info" : "error", "ran exercise", { file, args, exitCode: run.exitCode, ms: run.durationMs });
    }
  }
  runs.sort((a, b) => (a.file + a.args).localeCompare(b.file + b.args));
  fs.mkdirSync(path.dirname(outFile), { recursive: true });
  fs.writeFileSync(outFile, JSON.stringify({ generatedBy: "scripts/capture-exercises.mjs", runs }, null, 2) + "\n");
  log("info", "wrote captures", { count: runs.length, outFile: path.relative(root, outFile) });
}

main();
