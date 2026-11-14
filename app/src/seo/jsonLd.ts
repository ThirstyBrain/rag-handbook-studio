import { findAdr, findChapter, getHandbook } from "@/content/handbook";
import { toPlainText } from "@/content/parse/text";
import { matchPath } from "@/shared/router/router";
import { contentDates } from "./dates";
import { parseInterviewFaq } from "./faq";
import { getPageMeta } from "./pageMeta";
import { PUBLISHER, REPO_URL, SITE_DEFINITION, SITE_NAME, SITE_SUBTITLE } from "./siteConfig";
import { stripEvidence } from "./text";

type Json = Record<string, unknown>;

const organization = (siteUrl: string): Json => ({
  "@type": "Organization",
  "@id": `${siteUrl}/#publisher`,
  name: PUBLISHER.name,
  url: PUBLISHER.url,
  sameAs: [PUBLISHER.url, REPO_URL],
});

const website = (siteUrl: string): Json => ({
  "@type": "WebSite",
  "@id": `${siteUrl}/#website`,
  name: SITE_NAME,
  alternateName: SITE_SUBTITLE,
  description: SITE_DEFINITION,
  url: `${siteUrl}/`,
  inLanguage: "en",
  publisher: { "@id": `${siteUrl}/#publisher` },
});

function breadcrumbs(siteUrl: string, trail: { name: string; path: string }[]): Json {
  return {
    "@type": "BreadcrumbList",
    itemListElement: trail.map((t, i) => ({ "@type": "ListItem", position: i + 1, name: t.name, item: `${siteUrl}${t.path}` })),
  };
}

function techArticle(siteUrl: string, meta: { description: string; path: string }, headline: string, sourcePath: string, extra: Json = {}): Json {
  const dates = contentDates(sourcePath);
  return {
    "@type": "TechArticle",
    headline,
    description: meta.description,
    url: `${siteUrl}${meta.path}`,
    mainEntityOfPage: `${siteUrl}${meta.path}`,
    inLanguage: "en",
    proficiencyLevel: "Expert",
    author: { "@id": `${siteUrl}/#publisher` },
    publisher: { "@id": `${siteUrl}/#publisher` },
    isPartOf: { "@id": `${siteUrl}/#website` },
    ...(dates ? { datePublished: dates.published, dateModified: dates.modified } : {}),
    ...extra,
  };
}

/** JSON-LD graph members for a page. Built from the same data the page renders. */
export function buildJsonLd(rawPath: string, siteUrl: string): Json[] {
  const meta = getPageMeta(rawPath);
  if (!meta) return [];
  const hb = getHandbook();
  const base = [organization(siteUrl), website(siteUrl)];
  if (meta.path === "/") return base;

  const home = { name: SITE_NAME, path: "/" };
  const crumbs = (...rest: { name: string; path: string }[]) => breadcrumbs(siteUrl, [home, ...rest]);

  const chapterMatch = matchPath("/handbook/:slug", meta.path);
  if (chapterMatch) {
    const c = findChapter(chapterMatch.slug ?? "")!;
    const faq = parseInterviewFaq(c.markdown);
    const citedIds = [...new Set([...c.markdown.matchAll(/\bS\d+\b/g)].map((m) => m[0]))];
    const citations = citedIds
      .map((id) => hb.references.get(id)?.citation)
      .filter((x): x is string => Boolean(x))
      .map((x) => stripEvidence(toPlainText(x)));
    return [
      ...base,
      techArticle(siteUrl, meta, c.title, c.sourcePath, {
        wordCount: c.wordCount,
        timeRequired: `PT${c.readingMinutes}M`,
        ...(citations.length ? { citation: citations } : {}),
      }),
      crumbs({ name: "Handbook", path: "/handbook" }, { name: c.title, path: meta.path }),
      ...(faq.length
        ? [{ "@type": "FAQPage", mainEntity: faq.map((f) => ({ "@type": "Question", name: f.question, acceptedAnswer: { "@type": "Answer", text: f.answer } })) }]
        : []),
    ];
  }

  const decisionMatch = matchPath("/decisions/:id", meta.path);
  if (decisionMatch) {
    const adr = findAdr(decisionMatch.id ?? "")!;
    return [...base, techArticle(siteUrl, meta, `${adr.id}: ${adr.title}`, adr.sourcePath), crumbs({ name: "Decisions", path: "/decisions" }, { name: adr.id, path: meta.path })];
  }

  const label = meta.path.slice(1).replace(/^./, (s) => s.toUpperCase());
  const graph: Json[] = [
    ...base,
    { "@type": "WebPage", name: meta.title, description: meta.description, url: `${siteUrl}${meta.path}`, isPartOf: { "@id": `${siteUrl}/#website` } },
    crumbs({ name: label, path: meta.path }),
  ];

  if (meta.path === "/glossary") {
    graph.push({
      "@type": "DefinedTermSet",
      name: `${SITE_NAME} glossary`,
      url: `${siteUrl}/glossary`,
      hasDefinedTerm: hb.glossary.map((t) => ({
        "@type": "DefinedTerm",
        name: t.term,
        description: stripEvidence(toPlainText(t.definition)),
        url: `${siteUrl}/glossary#${t.slug}`,
        inDefinedTermSet: `${siteUrl}/glossary`,
      })),
    });
  }

  if (meta.path === "/exercises") {
    graph.push({
      "@type": "ItemList",
      itemListElement: hb.exercises.map((e, i) => ({
        "@type": "ListItem",
        position: i + 1,
        item: { "@type": "LearningResource", name: e.title || e.file, learningResourceType: "Exercise", programmingLanguage: "Python", inLanguage: "en", url: `${siteUrl}/exercises` },
      })),
    });
  }
  return graph;
}

/** Serialises a graph for a JSON-LD script tag; "<" is escaped so content can never close the tag. */
export function jsonLdScript(graph: Json[], path: string): string {
  if (!graph.length) return "";
  return `<script type="application/ld+json" data-path="${path}">${JSON.stringify({ "@context": "https://schema.org", "@graph": graph }).replace(/</g, "\\u003c")}</script>`;
}
