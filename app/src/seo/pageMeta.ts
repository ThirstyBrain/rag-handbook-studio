import { findAdr, findChapter, getHandbook } from "@/content/handbook";
import { firstSentence, toPlainText } from "@/content/parse/text";
import { matchPath } from "@/shared/router/router";
import { contentDates, latestModified } from "./dates";
import { META_DESCRIPTION_MAX, SITE_DESCRIPTION, SITE_NAME, SITE_TITLE } from "./siteConfig";
import { chapterDescription, stripEvidence, truncate } from "./text";

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
}

const suffix = ` | ${SITE_NAME}`;
const clampDescription = (s: string) => truncate(s, META_DESCRIPTION_MAX);

const STATIC_PAGES: Record<string, { title: string; description: string }> = {
  "/architecture": {
    title: `RAG Architecture Map: Ingestion to Generation${suffix}`,
    description: "A blueprint of the RAG indexing and query paths. Each stage links to the chapters, diagrams, decision records and terms behind it.",
  },
  "/lab": {
    title: `Hybrid Search Lab: BM25, Vectors and RRF${suffix}`,
    description: "Run a toy hybrid retrieval pipeline in your browser: BM25, a trigram stand-in for vectors, reciprocal rank fusion and nDCG, with every score explained.",
  },
  "/exercises": {
    title: `RAG Exercises With Real Output${suffix}`,
    description: "Runnable Python exercises from the handbook beside their captured output, plus knowledge-checkpoint questions for every chapter.",
  },
  "/glossary": {
    title: `RAG Glossary: Retrieval and LLM Terms${suffix}`,
    description: "Definitions of retrieval-augmented generation terms, from BM25 and chunking to reranking and RRF, each linked to the chapters that use them.",
  },
  "/references": {
    title: `RAG Handbook References and Sources${suffix}`,
    description: "Every source cited in the handbook, with its review status, linked back to the chapters that rely on it.",
  },
  "/about": {
    title: `About the Handbook and How Claims Are Verified${suffix}`,
    description: "Who the handbook is for, how every claim is labelled by its evidence, and how to report an error or suggest a correction.",
  },
};

/** Metadata for a URL path, or null when no page exists at that address. */
export function getPageMeta(rawPath: string): PageMeta | null {
  const path = rawPath.replace(/\/+$/, "") || "/";
  const hb = getHandbook();

  if (path === "/") return { path, title: SITE_TITLE, description: SITE_DESCRIPTION, ogType: "website", modified: latestModified() };

  if (path === "/handbook") {
    const written = hb.chapters.length;
    return {
      path,
      title: `Handbook Contents: ${written} RAG Chapters${suffix}`,
      description: clampDescription(`All ${written} written chapters of the RAG Architecture Handbook, grouped by part, with the ${hb.entries.length - written} still planned.`),
      ogType: "website",
      modified: latestModified(),
    };
  }

  const chapter = matchPath("/handbook/:slug", path);
  if (chapter) {
    const c = findChapter(chapter.slug ?? "");
    if (!c) return null;
    return {
      path: `/handbook/${c.slug}`,
      title: `${c.title}${suffix}`,
      description: chapterDescription(c, META_DESCRIPTION_MAX),
      ogType: "article",
      modified: contentDates(c.sourcePath)?.modified,
    };
  }

  if (path === "/decisions") {
    return {
      path,
      title: `RAG Architecture Decision Records${suffix}`,
      description: clampDescription(`${hb.adrs.length} architecture decision records for a production RAG system: context, options considered, the decision, trade-offs and when to reverse it.`),
      ogType: "website",
      modified: latestModified(),
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
      title: `${adr.id}: ${adr.title}${suffix}`,
      description: clampDescription(`${adr.status}. ${lede || `Architecture decision record ${adr.id}.`}`),
      ogType: "article",
      modified: contentDates(adr.sourcePath)?.modified,
    };
  }

  const fixed = STATIC_PAGES[path];
  return fixed ? { path, ...fixed, ogType: "website", modified: latestModified() } : null;
}

export const NOT_FOUND_META: PageMeta = {
  path: "/404",
  title: `Page not found${suffix}`,
  description: "No page exists at this address. Browse the handbook contents instead.",
  ogType: "website",
  noindex: true,
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
    "/decisions",
    ...hb.adrs.map((a) => `/decisions/${a.id}`),
    "/glossary",
    "/references",
    "/about",
  ];
}
