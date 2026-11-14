import { getHandbook } from "@/content/handbook";
import { EVIDENCE_LABELS, EVIDENCE_SHORT } from "@/content/parse/evidence";
import type { EvidenceKind } from "@/content/types";
import { AUTHOR, ISSUES_URL, REPO_URL, SITE_DEFINITION } from "@/seo/siteConfig";

export interface AboutSection {
  id: string;
  title: string;
  paragraphs: string[];
  list?: { term: string; text: string }[];
  link?: { href: string; label: string };
}

const EVIDENCE_ORDER: EvidenceKind[] = ["S", "X", "E", "V", "I", "A", "N"];

/** Plain data so the React page and the build-time static snapshot render identical text. */
export function aboutSections(): AboutSection[] {
  const hb = getHandbook();
  return [
    {
      id: "what-this-is",
      title: "What this handbook is",
      paragraphs: [
        SITE_DEFINITION,
        `It currently has ${hb.chapters.length} written chapters, ${hb.adrs.length} architecture decision records, ${hb.glossary.length} glossary terms and ${hb.exercises.length} runnable exercises. Every page on this site is rendered from the handbook's own Markdown, so the text here is the text in the repository.`,
      ],
    },
    {
      id: "who-its-for",
      title: "Who it is for",
      paragraphs: [
        "Software architects, solution architects, technical leads, principal engineers and AI platform architects who need to design, build, evaluate, secure and operate production RAG systems, and who want the trade-offs and failure modes stated rather than implied.",
      ],
    },
    {
      id: "how-claims-are-verified",
      title: "How claims are verified",
      paragraphs: ["Every significant claim carries a label that says what kind of evidence stands behind it. Performance figures are never presented without one."],
      list: EVIDENCE_ORDER.map((k) => ({ term: EVIDENCE_SHORT[k], text: EVIDENCE_LABELS[k] })),
    },
    {
      id: "maintained-by",
      title: "Who maintains it",
      paragraphs: [
        `The handbook and this reading application are written and maintained by ${AUTHOR.name} in one public repository. Chapters and the application are versioned together, so every change to a page is in the commit history.`,
        ...(AUTHOR.bio ? [AUTHOR.bio] : []),
      ],
      link: { href: REPO_URL, label: "View the repository" },
    },
    {
      id: "report-an-error",
      title: "Report an error or suggest a correction",
      paragraphs: ["If a claim is wrong, a source is out of date or an exercise does not run, open an issue naming the chapter and section. Corrections to claims are made in the handbook and noted in its changelog."],
      link: { href: ISSUES_URL, label: "Open an issue" },
    },
  ];
}
