import { findAdr, findChapter, getHandbook } from "@/content/handbook";
import { firstSentence, toPlainText } from "@/content/parse/text";
import { matchPath } from "@/shared/router/router";
import { contentDates, latestModified } from "./dates";
import { META_DESCRIPTION_MAX, SITE_DESCRIPTION, SITE_NAME, SITE_TITLE, TITLE_MAX, TITLE_SUFFIX } from "./siteConfig";
import { chapterDescription, composeDescription, fitTitle, stripEvidence } from "./text";

export interface PageMeta {
  /** Canonical path without a trailing slash. */
  path: string;
  title: string;
  description: string;
  ogType: "website" | "article";
  /** ISO date of the last content change, when known. */
  modified?: string;
  /** Pages that must not be indexed (unknown URLs). */
  noindex?: boolean;
  /** Social card text: a short eyebrow and the page's own heading. */
  card: { label: string; heading: string };
}

const title = (main: string) => fitTitle(main, TITLE_SUFFIX, TITLE_MAX);
const describe = (text: string, ...fillers: string[]) => composeDescription(text, fillers, META_DESCRIPTION_MAX);

const STATIC_PAGES: Record<string, { heading: string; label: string; description: string }> = {
  "/architecture": {
    heading: "RAG Architecture Map: Ingestion to Generation",
    label: "Architecture",
    description: "A blueprint of the RAG indexing and query paths, from ingestion to generation. Each stage links to the chapters, diagrams, decisions and terms behind it.",
  },
  "/lab": {
    heading: "Hybrid Search Lab: BM25, Vectors and RRF",
    label: "Interactive lab",
    description: "Run a toy hybrid retrieval pipeline in your browser: BM25, a trigram stand-in for vectors, reciprocal rank fusion and nDCG, with every score explained.",
  },
  "/exercises": {
    heading: "RAG Exercises With Real Output",
    label: "Exercises",
    description: "Runnable Python exercises from the handbook beside their captured output, plus knowledge-checkpoint questions for every chapter to test your understanding.",
  },
  "/glossary": {
    heading: "RAG Glossary: Retrieval and LLM Terms",
    label: "Glossary",
    description: "Definitions of retrieval-augmented generation terms, from BM25 and chunking to reranking and RRF, each linked to the chapters that use them in depth.",
  },
  "/references": {
    heading: "RAG Handbook References and Sources",
    label: "References",
    description: "Every source cited in the RAG Architecture Handbook, with its review status, linked back to the chapters that rely on it so you can check each claim.",
  },
  "/about": {
    heading: "About the Handbook and How Claims Are Verified",
    label: "About",
    description: "Who the RAG Architecture Handbook is for, how every claim is labelled by its evidence, who maintains it, and how to report an error or suggest a fix.",
  },
};

/** Metadata for a URL path, or null when no page exists at that address. */
export function getPageMeta(rawPath: string): PageMeta | null {
  const path = rawPath.replace(/\/+$/, "") || "/";
  const hb = getHandbook();

  if (path === "/") {
    return { path, title: SITE_TITLE, description: SITE_DESCRIPTION, ogType: "website", modified: latestModified(), card: { label: "Production RAG engineering guide", heading: SITE_NAME } };
  }

  if (path === "/handbook") {
    const written = hb.chapters.length;
    const heading = `Handbook Contents: ${written} RAG Chapters`;
    return {
      path,
      title: title(heading),
      description: describe(`All ${written} written chapters of the RAG Architecture Handbook, grouped by part, with the ${hb.entries.length - written} still planned.`, "From fundamentals to enterprise-scale retrieval systems.", "Evidence-labelled, with runnable exercises.", "Free to read."),
      ogType: "website",
      modified: latestModified(),
      card: { label: "Contents", heading },
    };
  }

  const chapter = matchPath("/handbook/:slug", path);
  if (chapter) {
    const c = findChapter(chapter.slug ?? "");
    if (!c) return null;
    return {
      path: `/handbook/${c.slug}`,
      title: title(c.title),
      description: chapterDescription(c, META_DESCRIPTION_MAX),
      ogType: "article",
      modified: contentDates(c.sourcePath)?.modified,
      card: { label: `Chapter ${c.number}`, heading: c.title },
    };
  }

  if (path === "/decisions") {
    const heading = "RAG Architecture Decision Records";
    return {
      path,
      title: title(heading),
      description: describe(`${hb.adrs.length} architecture decision records for a production RAG system: context, options considered, the decision, trade-offs and when to reverse it.`),
      ogType: "website",
      modified: latestModified(),
      card: { label: "Decisions", heading },
    };
  }

  const decision = matchPath("/decisions/:id", path);
  if (decision) {
    const adr = findAdr(decision.id ?? "");
    if (!adr) return null;
    const context = adr.sections.find((s) => s.kind === "context");
    const lede = context ? firstSentence(stripEvidence(toPlainText(context.markdown))) : "";
    return {
      path: `/decisions/${adr.id}`,
      title: title(`${adr.id}: ${adr.title}`),
      description: describe(`${adr.title}. ${adr.status} architecture decision. ${lede}`, "Context, options, trade-offs and when to reverse it.", "Part of the RAG Architecture Handbook.", "Evidence-labelled.", "Free to read."),
      ogType: "article",
      modified: contentDates(adr.sourcePath)?.modified,
      card: { label: adr.id, heading: adr.title },
    };
  }

  if (path === "/interview-questions") {
    const heading = "RAG Interview Questions With Model Answers";
    return {
      path,
      title: title(heading),
      description: describe("RAG interview questions with concise model answers, collected from every chapter of the handbook and grouped by topic, each linked to the full explanation."),
      ogType: "website",
      modified: latestModified(),
      card: { label: "Interview prep", heading },
    };
  }

  const fixed = STATIC_PAGES[path];
  return fixed
    ? { path, title: title(fixed.heading), description: fixed.description, ogType: "website", modified: latestModified(), card: { label: fixed.label, heading: fixed.heading } }
    : null;
}

export const NOT_FOUND_META: PageMeta = {
  path: "/404",
  title: `Page not found${TITLE_SUFFIX}`,
  description: "No page exists at this address. Browse the handbook contents instead.",
  ogType: "website",
  noindex: true,
  card: { label: "404", heading: "Page not found" },
};

/** Every canonical, indexable path. Planned chapters that have no file are never listed. */
export function listIndexablePaths(): string[] {
  const hb = getHandbook();
  return [
    "/",
    "/handbook",
    ...hb.chapters.map((c) => `/handbook/${c.slug}`),
    "/architecture",
    "/lab",
    "/exercises",
    "/interview-questions",
    "/decisions",
    ...hb.adrs.map((a) => `/decisions/${a.id}`),
    "/glossary",
    "/references",
    "/about",
  ];
}
