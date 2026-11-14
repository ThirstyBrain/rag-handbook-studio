import { getHandbook } from "@/content/handbook";
import { escapeHtml } from "@/shared/markdown/highlight";
import { buildJsonLd, jsonLdScript } from "./jsonLd";
import { renderCard } from "./ogCard";
import { getPageMeta, listIndexablePaths, NOT_FOUND_META, type PageMeta } from "./pageMeta";
import { renderSnapshot } from "./snapshot";
import { ogFileName } from "./ogPath";
import { OG_IMAGE_DIR, SITE_DEFINITION, SITE_NAME, SITE_SUBTITLE } from "./siteConfig";

export interface BuildOptions {
  /** Absolute origin without a trailing slash, e.g. "https://example.com". */
  siteUrl: string;
}

export interface StaticPage {
  /** URL path, e.g. "/handbook/01-traditional-llm-vs-rag". */
  path: string;
  /** Tags to add inside <head>; replaces the template's title and description. */
  head: string;
  /** Static content for #root. */
  body: string;
}

export interface OgCardFile {
  /** File name inside the og folder, e.g. "handbook-01-traditional-llm-vs-rag.png". */
  file: string;
  png: Buffer;
}

const a = escapeHtml;

export function buildHead(meta: PageMeta, { siteUrl }: BuildOptions, jsonLd = ""): string {
  const url = `${siteUrl}${meta.path === "/" ? "/" : meta.path}`;
  const image = meta.noindex ? "" : `${siteUrl}${OG_IMAGE_DIR}/${ogFileName(meta.path)}`;
  const tags = [
    `<title>${a(meta.title)}</title>`,
    `<meta name="description" content="${a(meta.description)}" />`,
    meta.noindex ? `<meta name="robots" content="noindex" />` : `<link rel="canonical" href="${a(url)}" />`,
    `<meta property="og:site_name" content="${a(SITE_NAME)}" />`,
    `<meta property="og:type" content="${meta.ogType}" />`,
    `<meta property="og:title" content="${a(meta.title)}" />`,
    `<meta property="og:description" content="${a(meta.description)}" />`,
    `<meta property="og:url" content="${a(url)}" />`,
    `<meta property="og:locale" content="en_US" />`,
    meta.modified && meta.ogType === "article" ? `<meta property="article:modified_time" content="${a(meta.modified)}" />` : "",
    image
      ? `<meta property="og:image" content="${a(image)}" />\n    <meta property="og:image:type" content="image/png" />\n    <meta property="og:image:width" content="1200" />\n    <meta property="og:image:height" content="630" />\n    <meta property="og:image:alt" content="${a(meta.card.heading)}" />`
      : "",
    `<meta name="twitter:card" content="${image ? "summary_large_image" : "summary"}" />`,
    `<meta name="twitter:title" content="${a(meta.title)}" />`,
    `<meta name="twitter:description" content="${a(meta.description)}" />`,
    image ? `<meta name="twitter:image" content="${a(image)}" />` : "",
    jsonLd,
  ];
  return tags.filter(Boolean).join("\n    ");
}

export function buildPages(options: BuildOptions): StaticPage[] {
  return listIndexablePaths().map((path) => {
    const meta = getPageMeta(path)!;
    return { path: meta.path, head: buildHead(meta, options, jsonLdScript(buildJsonLd(path, options.siteUrl), meta.path)), body: renderSnapshot(meta.path) };
  });
}

/** One social card per indexable page, titled with the page's own heading. */
export function buildOgCards({ siteUrl }: BuildOptions): OgCardFile[] {
  const footer = new URL(siteUrl).host;
  return listIndexablePaths().map((path) => {
    const { card } = getPageMeta(path)!;
    return { file: ogFileName(path), png: renderCard({ ...card, footer }) };
  });
}

/** The 404 page is the plain app shell: the router shows its "not found" screen. It is never indexed. */
export function buildNotFoundPage(options: BuildOptions): Omit<StaticPage, "path"> {
  return { head: buildHead(NOT_FOUND_META, options), body: "" };
}

const dateOnly = (iso: string) => iso.slice(0, 10);

export function buildSitemap({ siteUrl }: BuildOptions): string {
  const urls = listIndexablePaths().map((path) => {
    const meta = getPageMeta(path)!;
    const loc = `${siteUrl}${meta.path === "/" ? "/" : meta.path}`;
    return `  <url><loc>${a(loc)}</loc>${meta.modified ? `<lastmod>${dateOnly(meta.modified)}</lastmod>` : ""}</url>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join("\n")}\n</urlset>\n`;
}

export function buildRobots({ siteUrl }: BuildOptions): string {
  return `User-agent: *\nAllow: /\n\nSitemap: ${siteUrl}/sitemap.xml\n`;
}

/** A plain-text map of the site for language-model tools (llms.txt convention). */
export function buildLlmsTxt({ siteUrl }: BuildOptions): string {
  const hb = getHandbook();
  const lines = [
    `# ${SITE_NAME}`,
    "",
    `> ${SITE_DEFINITION}`,
    "",
    `${SITE_SUBTITLE}. Every claim is labelled by its evidence: reviewed source, executed in the repository, engineering reasoning, assumption or illustrative.`,
    "",
    "## Chapters",
    ...hb.chapters.map((c) => `- [${c.title}](${siteUrl}/handbook/${c.slug}): ${getPageMeta(`/handbook/${c.slug}`)!.description}`),
    "",
    "## Reference",
    `- [Contents](${siteUrl}/handbook): all chapters by part`,
    `- [Interview questions](${siteUrl}/interview-questions): model answers collected from every chapter`,
    `- [Architecture decisions](${siteUrl}/decisions): ${hb.adrs.length} decision records`,
    `- [Glossary](${siteUrl}/glossary): ${hb.glossary.length} defined terms`,
    `- [References](${siteUrl}/references): reviewed sources`,
    `- [Exercises](${siteUrl}/exercises): runnable scripts with captured output`,
    `- [About](${siteUrl}/about): audience, evidence labels, how to report an error`,
    "",
  ];
  return lines.join("\n");
}
