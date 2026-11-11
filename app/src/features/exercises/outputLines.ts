/** Classifies lines of captured exercise output so the terminal view can give them structure. */
export type LineKind = "heading" | "ok" | "pass" | "error" | "note" | "table" | "plain";

export interface OutputLine {
  kind: LineKind;
  text: string;
}

export function classifyLine(text: string): LineKind {
  const t = text.trim();
  if (!t) return "plain";
  if (/^==+\s.*\s==+$/.test(t) || /^--\s.*\s--$/.test(t)) return "heading";
  if (/^all (assertions|checks|tests) passed/i.test(t)) return "pass";
  if (/traceback|error:|assertionerror|\bFAIL(ED)?\b/i.test(t)) return "error";
  if (/(:\s*OK|\bOK)\s*$/.test(t)) return "ok";
  if (/^\*|^note[:\s]|illustrative|not a real/i.test(t)) return "note";
  if (/\S\s{2,}\S/.test(t)) return "table";
  return "plain";
}

export function classifyOutput(stdout: string): OutputLine[] {
  const lines = stdout.replace(/\n$/, "").split("\n");
  return lines.map((text) => ({ text, kind: classifyLine(text) }));
}

export async function sha256Hex(text: string): Promise<string | null> {
  try {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;
  }
}
