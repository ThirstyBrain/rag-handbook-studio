#!/usr/bin/env node
/**
 * Records "published" and "last updated" dates for chapters and ADRs in app/content-dates.json, using the
 * file timestamps on this machine. Run it on the machine where you edit the handbook, after editing, and
 * commit the result. A file is (re)recorded only when it is new or its content hash changed, so unchanged
 * chapters keep their dates.
 *
 * Usage: node scripts/record-content-dates.mjs
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const handbook = path.resolve(root, "../handbook");
const outFile = path.join(root, "content-dates.json");
const sources = [
  { dir: "docs/chapters", pattern: /\.md$/ },
  { dir: "adr", pattern: /^ADR-.*\.md$/ },
];

const hash = (text) => createHash("sha256").update(text.replace(/\r\n/g, "\n")).digest("hex");
const baseline = fs.existsSync(outFile) ? JSON.parse(fs.readFileSync(outFile, "utf8")) : {};
const next = {};
let updated = 0;

for (const { dir, pattern } of sources) {
  for (const name of fs.readdirSync(path.join(handbook, dir)).filter((f) => pattern.test(f)).sort()) {
    const key = `${dir}/${name}`;
    const file = path.join(handbook, key);
    const sha256 = hash(fs.readFileSync(file, "utf8"));
    const previous = baseline[key];
    if (previous && previous.sha256 === sha256) {
      next[key] = previous;
      continue;
    }
    const stat = fs.statSync(file);
    const modified = stat.mtime.toISOString();
    const created = new Date(Math.min(stat.birthtimeMs || stat.mtimeMs, stat.mtimeMs)).toISOString();
    next[key] = { published: previous?.published ?? created, modified, sha256 };
    updated += 1;
  }
}

fs.writeFileSync(outFile, `${JSON.stringify(next, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ level: "info", scope: "record-content-dates", message: "recorded", files: Object.keys(next).length, updated }));
