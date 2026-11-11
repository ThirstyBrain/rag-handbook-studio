import type { EvidenceKind } from "../types";

/**
 * The handbook marks every significant claim with an evidence tag (see the chapter legends):
 * [S#] source, [E] engineering reasoning, [A] assumption, [I] illustrative, [X] executed,
 * [V] vendor-reported, [N] not researched. Tags can be combined: [E, S76].
 */
export const EVIDENCE_LABELS: Record<EvidenceKind, string> = {
  S: "Supported by a reviewed source",
  E: "Engineering recommendation or reasoning",
  A: "Assumption",
  I: "Illustrative, not executed",
  X: "Executed and verified in the handbook repository",
  V: "Vendor-reported",
  N: "Not researched",
};

export const EVIDENCE_SHORT: Record<EvidenceKind, string> = {
  S: "Source",
  E: "Reasoning",
  A: "Assumption",
  I: "Illustrative",
  X: "Executed",
  V: "Vendor",
  N: "Not researched",
};

const TOKEN = String.raw`(?:S\d+|[EAIXVN])`;
/** Matches a whole tag such as "[X]" or "[E, S76]"; never a Markdown link "[X](...)". */
export const EVIDENCE_TAG = new RegExp(String.raw`\[(${TOKEN}(?:\s*,\s*${TOKEN})*)\](?!\()`, "g");

export interface EvidenceToken {
  kind: EvidenceKind;
  /** Source id for kind "S", e.g. "S67". */
  ref?: string;
}

export function parseEvidenceTag(inner: string): EvidenceToken[] {
  return inner.split(/\s*,\s*/).map((t) => (t.startsWith("S") ? { kind: "S", ref: t } : { kind: t as EvidenceKind }));
}

export function countEvidence(md: string): Partial<Record<EvidenceKind, number>> {
  const counts: Partial<Record<EvidenceKind, number>> = {};
  const withoutCode = md.replace(/```[\s\S]*?```/g, "");
  for (const m of withoutCode.matchAll(EVIDENCE_TAG)) {
    for (const tok of parseEvidenceTag(m[1]!)) counts[tok.kind] = (counts[tok.kind] ?? 0) + 1;
  }
  return counts;
}
