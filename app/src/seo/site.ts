import { getHandbook } from "@/content/handbook";
import { escapeHtml } from "@/shared/markdown/highlight";
import { buildJsonLd, jsonLdScript } from "./jsonLd";
import { getPageMeta, listIndexablePaths, NOT_FOUND_META, type PageMeta } from "./pageMeta";
import { renderSnapshot } from "./snapshot";
import { OG_IMAGE_PATH, SITE_DEFINITION, SITE_NAME, SITE_SUBTITLE } from "./siteConfig";

export interface BuildOptions {
  /** Absolute origin without a trailing slash, e.g. "https://example.com". */
  siteUrl: string;
  /** Whether public/og-image.png exists. */
  hasOgImage: boolean;
}

export interface StaticPage {
  /** URL path, e.g. "/handbook/01-traditional-llm-vs-rag". */
  path: string;
  /** Tags to add inside <head>; replaces the template's title and description. */
  head: string;
  /** Static content for #root. */
  body: string;
}

const a = escapeHtml;

export function buildHead(meta: PageMeta, { siteUrl, hasOgImage }: BuildOptions, jsonLd = ""): string {
  const url = `${siteUrl}${meta.path === "/" ? "/" : meta.path}`;
  const image = hasOgImage ? `${siteUrl}${OG_IMAGE_PATH}` : "";
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
    image ? `<meta property="og:image" content="${a(image)}" />\n    <meta property="og:image:width" content="1200" />\n    <meta property="og:image:height" content="630" />\n    <meta property="og:image:alt" content="${a(SITE_NAME)}" />` : "",
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
    `- [Architecture decisions](${siteUrl}/decisions): ${hb.adrs.length} decision records`,
    `- [Glossary](${siteUrl}/glossary): ${hb.glossary.length} defined terms`,
    `- [References](${siteUrl}/references): reviewed sources`,
    `- [Exercises](${siteUrl}/exercises): runnable scripts with captured output`,
    `- [About](${siteUrl}/about): audience, evidence labels, how to report an error`,
    "",
  ];
  return lines.join("\n");
}
