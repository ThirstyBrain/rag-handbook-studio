import { chapterHref, findAdr, findChapter, getHandbook } from "@/content/handbook";
import { handbookRenderContext } from "@/content/renderContext";
import { toPlainText } from "@/content/parse/text";
import type { Chapter } from "@/content/types";
import { STAGES } from "@/features/architecture/stages";
import { aboutSections } from "@/features/about/aboutContent";
import { interviewGroups } from "@/features/interview/interviewData";
import { CORPUS, QRELS, SOURCE_FILE } from "@/features/playground/domain/corpus";
import { HONESTY, HOW_TO_READ, METHODS } from "@/features/playground/labContent";
import { escapeHtml } from "@/shared/markdown/highlight";
import { renderMarkdown } from "@/shared/markdown/render";
import { matchPath } from "@/shared/router/router";
import { contentDates, formatDate } from "./dates";
import { chapterTldr, stripEvidence } from "./text";
import { AUTHOR, SITE_DEFINITION, SITE_NAME, SITE_SUBTITLE } from "./siteConfig";

/**
 * Static, crawlable HTML for each route. It is written into #root at build time so search and AI
 * crawlers that never run JavaScript still receive the headings, text and links. React replaces it on
 * load, so what a visitor sees is the live app and what a crawler reads is the same content.
 */

const e = escapeHtml;
const link = (href: string, text: string) => `<a href="${e(href)}">${e(text)}</a>`;
const plain = (md: string) => e(stripEvidence(toPlainText(md)));

/** Interactive-only markup that is noise in a static page. */
function simplify(html: string): string {
  return html
    .replace(/<figure class="diagram"[\s\S]*?<\/figure>\n?/g, "")
    .replace(/<button type="button" class="code__copy" data-copy>Copy<\/button>/g, "")
    .replace(/<div class="exercise-slot"[^>]*><\/div>\n?/g, "");
}

function renderBody(md: string): string {
  return simplify(renderMarkdown(md, handbookRenderContext()).html);
}

function siteNav(): string {
  const main = [
    ["/handbook", "Contents"],
    ["/architecture", "Architecture map"],
    ["/lab", "Retrieval lab"],
    ["/exercises", "Exercises"],
    ["/interview-questions", "Interview questions"],
    ["/decisions", "Decisions"],
    ["/glossary", "Glossary"],
    ["/references", "References"],
    ["/about", "About"],
  ] as const;
  return `<header><p>${link("/", SITE_NAME)}</p><nav aria-label="Primary"><ul>${main.map(([h, t]) => `<li>${link(h, t)}</li>`).join("")}</ul></nav></header>`;
}

/** After the page content, so crawlers meet the page's own text first; gives every page a path to every chapter. */
function chapterNav(): string {
  const hb = getHandbook();
  return `<nav aria-label="All chapters"><h2>All chapters</h2><ol>${hb.chapters.map((c) => `<li>${link(chapterHref(c), c.title)}</li>`).join("")}</ol></nav>`;
}

function crumbs(items: { href?: string; text: string }[]): string {
  return `<nav aria-label="Breadcrumb"><ol>${items.map((i) => `<li>${i.href ? link(i.href, i.text) : e(i.text)}</li>`).join("")}</ol></nav>`;
}

function home(): string {
  const hb = getHandbook();
  const parts = hb.parts
    .map((p) => {
      const chapters = hb.chapters.filter((c) => c.partId === p.id);
      if (!chapters.length) return "";
      return `<section><h3>Part ${e(p.roman)}: ${e(p.title)}</h3><ul>${chapters.map((c) => `<li>${link(chapterHref(c), `${c.number}. ${c.title}`)}</li>`).join("")}</ul></section>`;
    })
    .join("");
  return `<h1>${e(SITE_NAME)}</h1><p>${e(SITE_SUBTITLE)}</p><p>${e(SITE_DEFINITION)}</p><h2>Read the handbook</h2>${parts}`;
}

function contents(): string {
  const hb = getHandbook();
  const parts = hb.parts
    .map((p) => {
      const entries = hb.entries.filter((en) => en.partId === p.id);
      if (!entries.length) return "";
      const items = entries
        .map((en) => {
          const written = findChapter(en.number);
          return `<li>${written ? link(chapterHref(written), `${en.number}. ${en.title}`) : `${en.number}. ${e(en.title)} (planned)`}</li>`;
        })
        .join("");
      return `<section id="${e(p.id)}"><h2>Part ${e(p.roman)}: ${e(p.title)}</h2><ul>${items}</ul></section>`;
    })
    .join("");
  return `<h1>Handbook contents</h1><p>${hb.chapters.length} written chapters and ${hb.entries.length - hb.chapters.length} planned, grouped by part.</p>${parts}`;
}

function chapterPage(c: Chapter): string {
  const hb = getHandbook();
  const part = hb.parts.find((p) => p.id === c.partId);
  const i = hb.chapters.findIndex((x) => x.number === c.number);
  const prev = hb.chapters[i - 1];
  const next = hb.chapters[i + 1];
  const dates = contentDates(c.sourcePath);
  const tldr = chapterTldr(c);
  const objectives = c.objectives.length ? `<h2>Learning objectives</h2><ol>${c.objectives.map((o) => `<li>${e(stripEvidence(o))}</li>`).join("")}</ol>` : "";
  return (
    crumbs([{ href: "/handbook", text: "Handbook" }, ...(part ? [{ href: `/handbook#${part.id}`, text: `Part ${part.roman}: ${part.title}` }] : []), { text: c.title }]) +
    `<article><h1>${e(c.title)}</h1>` +
    (tldr ? `<p><strong>In short:</strong> ${e(tldr)}</p>` : "") +
    `<p>By ${link(AUTHOR.url, AUTHOR.name)}. ${c.readingMinutes} min read${dates ? `. Last updated <time datetime="${e(dates.modified)}">${e(formatDate(dates.modified))}</time>` : ""}.</p>` +
    objectives +
    renderBody(c.markdown) +
    `</article><nav aria-label="Previous and next chapter">${prev ? `<p>Previous: ${link(chapterHref(prev), prev.title)}</p>` : ""}${next ? `<p>Next: ${link(chapterHref(next), next.title)}</p>` : ""}</nav>`
  );
}

function decisions(): string {
  const hb = getHandbook();
  return `<h1>Architecture decisions</h1><p>${hb.adrs.length} records of what the reference system will do, what else was considered, and what evidence would change the decision.</p><ul>${hb.adrs.map((a) => `<li>${link(`/decisions/${a.id}`, `${a.id}: ${a.title}`)} (${e(a.status)})</li>`).join("")}</ul>`;
}

function decision(id: string): string {
  const adr = findAdr(id)!;
  const sections = adr.sections.filter((s) => s.kind !== "status").map((s) => `<section><h2>${e(s.title)}</h2>${renderBody(s.markdown)}</section>`).join("");
  return crumbs([{ href: "/decisions", text: "Decisions" }, { text: adr.id }]) + `<article><h1>${e(adr.id)}: ${e(adr.title)}</h1><p>Status: ${e(adr.statusLine || adr.status)}</p>${sections}</article>`;
}

function glossary(): string {
  const hb = getHandbook();
  const terms = hb.glossary.map((t) => `<dt id="${e(t.slug)}">${e(t.term)}</dt><dd>${plain(t.definition)}</dd>`).join("");
  return `<h1>Glossary</h1><p>${hb.glossary.length} terms used across the handbook.</p><dl>${terms}</dl>`;
}

function references(): string {
  const hb = getHandbook();
  const all = [...hb.references.values()].sort((a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1)));
  const items = all.map((r) => `<li id="${e(r.id)}">${e(r.id)}: ${plain(r.citation.replace(/\s*https?:\/\/\S+/g, ""))}${r.url ? ` ${link(r.url, r.url)}` : ""}</li>`).join("");
  return `<h1>References</h1><p>${all.length} reviewed sources behind the [S#] marks in the chapters.</p><ol>${items}</ol>`;
}

function exercises(): string {
  const hb = getHandbook();
  const items = hb.exercises
    .map((x) => {
      const c = x.chapter ? findChapter(x.chapter) : undefined;
      return `<li><code>${e(x.file)}</code>: ${e(x.title)}${c ? ` (${link(chapterHref(c), `chapter ${c.number}`)})` : ""}</li>`;
    })
    .join("");
  return `<h1>Exercises</h1><p>Runnable standard-library Python scripts from the handbook, each shown with its source and real captured output.</p><ul>${items}</ul>`;
}

function architecture(): string {
  const hb = getHandbook();
  const lane = (l: string, title: string) =>
    `<h2>${title}</h2><ol>${STAGES.filter((s) => s.lane === l)
      .map((s) => `<li>${e(s.name)}: ${s.chapters.map((n) => findChapter(n)).filter((c): c is Chapter => Boolean(c)).map((c) => link(chapterHref(c), c.title)).join(", ")}</li>`)
      .join("")}</ol>`;
  return `<h1>RAG architecture map</h1><p>The indexing path and the query path of a production RAG system, with the chapters, diagrams and decisions behind each stage. ${hb.chapters.length} chapters are mapped.</p>${lane("offline", "Indexing path")}${lane("online", "Query path")}${lane("cross", "Across both paths")}`;
}

function lab(): string {
  const corpus = Object.entries(CORPUS).map(([id, text]) => `<li>${e(id)}: ${e(text)}</li>`).join("");
  const methods = METHODS.map((m) => `<dt>${e(m.label)}</dt><dd>${e(m.explain)}</dd>`).join("");
  const chapter9 = findChapter(9);
  return (
    `<h1>Retrieval lab</h1><p>A toy hybrid retrieval pipeline that runs in your browser. It ports the chapter 9 exercise: BM25 for keyword matching, a trigram stand-in for vector similarity, reciprocal rank fusion and min-max fusion to combine them, per-term score explanations and nDCG@3. Interactive controls need JavaScript.</p>` +
    `<h2>The four methods</h2><dl>${methods}</dl>` +
    `<h2>How to read the results</h2>${HOW_TO_READ.map((p) => `<p>${e(p)}</p>`).join("")}` +
    `<h2>Example questions</h2><ul>${Object.keys(QRELS).map((q) => `<li>${e(q)}</li>`).join("")}</ul>` +
    `<h2>The corpus</h2><ol>${corpus}</ol>` +
    `<h2>What this is, and is not</h2><p>${e(HONESTY.before)} <code>${e(SOURCE_FILE)}</code> ${e(HONESTY.after)}</p>` +
    (chapter9 ? `<p>${link(chapterHref(chapter9), "Read Chapter 9, Hybrid Search")}. ${link("/exercises#ch09_hybrid_search", "See the script and its output")}.</p>` : "")
  );
}

function interview(): string {
  const groups = interviewGroups();
  const total = groups.reduce((sum, g) => sum + g.items.length, 0);
  const sections = groups
    .map(({ chapter, items }) => `<section id="${e(chapter.slug)}"><h2>${link(chapterHref(chapter), `Chapter ${chapter.number}: ${chapter.title}`)}</h2>${items.map((i) => `<h3>${e(i.question)}</h3><p>${e(i.answer)}</p>`).join("")}</section>`)
    .join("");
  return `<h1>RAG interview questions</h1><p>${total} questions with concise model answers from ${groups.length} chapters.</p>${sections}`;
}

function about(): string {
  return (
    `<h1>About the handbook</h1>` +
    aboutSections()
      .map((s) => `<section id="${e(s.id)}"><h2>${e(s.title)}</h2>${s.paragraphs.map((p) => `<p>${e(p)}</p>`).join("")}${s.list ? `<dl>${s.list.map((l) => `<dt>${e(l.term)}</dt><dd>${e(l.text)}</dd>`).join("")}</dl>` : ""}${s.link ? `<p>${link(s.link.href, s.link.label)}</p>` : ""}</section>`)
      .join("")
  );
}

/** HTML for the page at `path`, wrapped with site navigation. Returns "" for unknown paths. */
export function renderSnapshot(path: string): string {
  let main: string | null = null;
  const chapter = matchPath("/handbook/:slug", path);
  const adr = matchPath("/decisions/:id", path);
  if (path === "/") main = home();
  else if (path === "/handbook") main = contents();
  else if (chapter) main = chapterPage(findChapter(chapter.slug ?? "")!);
  else if (path === "/decisions") main = decisions();
  else if (adr) main = decision(adr.id ?? "");
  else if (path === "/glossary") main = glossary();
  else if (path === "/references") main = references();
  else if (path === "/exercises") main = exercises();
  else if (path === "/architecture") main = architecture();
  else if (path === "/lab") main = lab();
  else if (path === "/interview-questions") main = interview();
  else if (path === "/about") main = about();
  if (main === null) return "";
  return `<div data-seo-snapshot>${siteNav()}<main>${main}</main>${chapterNav()}</div>`;
}
