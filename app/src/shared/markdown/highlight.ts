import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import json from "highlight.js/lib/languages/json";
import plaintext from "highlight.js/lib/languages/plaintext";
import python from "highlight.js/lib/languages/python";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import yaml from "highlight.js/lib/languages/yaml";

hljs.registerLanguage("bash", bash);
hljs.registerLanguage("json", json);
hljs.registerLanguage("plaintext", plaintext);
hljs.registerLanguage("python", python);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("yaml", yaml);

const ALIASES: Record<string, string> = { text: "plaintext", txt: "plaintext", sh: "bash", shell: "bash", py: "python", ts: "typescript", "": "plaintext" };

export const LANGUAGE_LABELS: Record<string, string> = {
  bash: "Shell",
  json: "JSON",
  plaintext: "Text",
  python: "Python",
  sql: "SQL",
  typescript: "TypeScript",
  yaml: "YAML",
};

export function normaliseLanguage(lang: string | undefined): string {
  const l = (lang ?? "").trim().toLowerCase().split(/\s+/)[0] ?? "";
  const resolved = ALIASES[l] ?? l;
  return hljs.getLanguage(resolved) ? resolved : "plaintext";
}

export function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** Returns highlighted HTML (already escaped). */
export function highlight(code: string, lang: string | undefined): { html: string; language: string } {
  const language = normaliseLanguage(lang);
  if (language === "plaintext") return { html: escapeHtml(code), language };
  return { html: hljs.highlight(code, { language, ignoreIllegals: true }).value, language };
}
