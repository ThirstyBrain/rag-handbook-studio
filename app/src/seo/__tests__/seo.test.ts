import { describe, expect, it } from "vitest";
import { getHandbook } from "@/content/handbook";
import { parseInterviewFaq } from "../faq";
import { buildJsonLd, jsonLdScript } from "../jsonLd";
import { getPageMeta, listIndexablePaths } from "../pageMeta";
import { META_DESCRIPTION_MAX, TITLE_MAX } from "../siteConfig";
import { renderCard } from "../ogCard";
import { ogFileName } from "../ogPath";
import { buildOgCards, buildPages, buildRobots, buildSitemap } from "../site";
import { renderSnapshot } from "../snapshot";
import { chapterTldr, stripEvidence, truncate } from "../text";

const options = { siteUrl: "https://example.test" };
const wordCount = (s: string) => s.split(/\s+/).filter(Boolean).length;

describe("text helpers", () => {
  it("strips evidence tags without leaving stray spaces", () => {
    expect(stripEvidence("RAG is cheaper [S21, E]. Use it [X].")).toBe("RAG is cheaper. Use it.");
  });

  it("truncates at a sentence when one fits, otherwise at a word with an ellipsis", () => {
    expect(truncate("First sentence here. Second one that is long.", 30)).toBe("First sentence here.");
    const cut = truncate("alpha beta gamma delta epsilon zeta", 20);
    expect(cut.endsWith("…")).toBe(true);
    expect(cut.length).toBeLessThanOrEqual(21);
  });

  it("builds a summary of whole sentences, at most 60 words", () => {
    const summary = Array.from({ length: 12 }, (_, i) => `Sentence number ${i} has exactly seven words in it.`).join(" ");
    const tldr = chapterTldr({ summary, problem: "" });
    expect(wordCount(tldr)).toBeGreaterThanOrEqual(40);
    expect(wordCount(tldr)).toBeLessThanOrEqual(60);
    expect(tldr.endsWith(".")).toBe(true);
  });
});

describe("interview FAQ", () => {
  const md = [
    "## 1.18 Interview Questions",
    "",
    "1. **Why fine-tune?** *Model answer:* Fine-tuning changes the model's behaviour, not what it knows, so it cannot cite sources or follow permissions [S22]. *Follow-up:* When both? *Common wrong answer:* \"Always.\"",
    "2. **Why not just add scores?** Different scales mean the larger one dominates, so normalise first or use rank fusion instead [X].",
    "3. **No model answer here?** See §1.8.",
    "",
    "## 1.19 Next",
  ].join("\n");

  it("extracts labelled and inline answers, and skips items that only point elsewhere", () => {
    expect(parseInterviewFaq(md)).toEqual([
      { question: "Why fine-tune?", answer: "Fine-tuning changes the model's behaviour, not what it knows, so it cannot cite sources or follow permissions." },
      { question: "Why not just add scores?", answer: "Different scales mean the larger one dominates, so normalise first or use rank fusion instead." },
    ]);
  });

  it("finds answers in most real chapters", () => {
    const withFaq = getHandbook().chapters.filter((c) => parseInterviewFaq(c.markdown).length > 0);
    expect(withFaq.length).toBeGreaterThanOrEqual(25);
  });

  it("returns nothing when the chapter has no interview section", () => {
    expect(parseInterviewFaq("## Summary\n\ntext")).toEqual([]);
  });
});

describe("page metadata for the real handbook", () => {
  const paths = listIndexablePaths();

  it("resolves every indexable path and rejects unknown ones", () => {
    for (const p of paths) expect(getPageMeta(p), p).not.toBeNull();
    expect(getPageMeta("/handbook/not-a-chapter")).toBeNull();
    expect(getPageMeta("/robots.txt")).toBeNull();
  });

  it("gives every page a unique title (at most 60 characters) and a 140-155 character description", () => {
    const metas = paths.map((p) => getPageMeta(p)!);
    for (const m of metas) {
      expect(m.title.length, `${m.path} title`).toBeLessThanOrEqual(TITLE_MAX + 1);
      expect(m.description.length, `${m.path} description`).toBeGreaterThanOrEqual(135);
      expect(m.description.length, `${m.path} description`).toBeLessThanOrEqual(META_DESCRIPTION_MAX + 1);
    }
    expect(new Set(metas.map((m) => m.title)).size).toBe(metas.length);
    expect(new Set(metas.map((m) => m.description)).size).toBe(metas.length);
  });

  it("lists only written chapters", () => {
    const hb = getHandbook();
    const chapterPaths = paths.filter((p) => p.startsWith("/handbook/"));
    expect(chapterPaths).toHaveLength(hb.chapters.length);
  });
});

describe("static output", () => {
  it("prerenders a non-empty body with one h1 for every indexable path", () => {
    for (const p of listIndexablePaths()) {
      const html = renderSnapshot(p);
      expect(html, p).not.toBe("");
      expect((html.match(/<h1[ >]/g) ?? []).length, p).toBe(1);
    }
    expect(renderSnapshot("/nope")).toBe("");
  });

  it("emits a canonical link and valid JSON-LD on each page, and never a closing script tag inside it", () => {
    for (const page of buildPages(options)) {
      expect(page.head, page.path).toContain(`<link rel="canonical" href="https://example.test${page.path === "/" ? "/" : page.path}"`);
      const json = /<script type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/.exec(page.head)?.[1];
      expect(json, page.path).toBeTruthy();
      expect(() => JSON.parse(json!), page.path).not.toThrow();
    }
  });

  it("marks up chapters as TechArticle with breadcrumbs", () => {
    const first = getHandbook().chapters[0]!;
    const types = buildJsonLd(`/handbook/${first.slug}`, options.siteUrl).map((n) => n["@type"]);
    expect(types).toContain("TechArticle");
    expect(types).toContain("BreadcrumbList");
  });

  it("escapes angle brackets in JSON-LD", () => {
    expect(jsonLdScript([{ "@type": "Thing", name: "</script><b>" }], "/x")).not.toContain("</script><b>");
  });

  it("lists exactly the indexable paths in the sitemap and points robots.txt at it", () => {
    const sitemap = buildSitemap(options);
    expect((sitemap.match(/<loc>/g) ?? []).length).toBe(listIndexablePaths().length);
    expect(buildRobots(options)).toContain("Sitemap: https://example.test/sitemap.xml");
  });
});

describe("social cards", () => {
  it("renders a valid 1200x630 PNG", () => {
    const png = renderCard({ label: "Chapter 9", heading: "Hybrid Search: BM25 + vectors", footer: "example.test" });
    expect(png.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
    expect(png.readUInt32BE(16)).toBe(1200);
    expect(png.readUInt32BE(20)).toBe(630);
  });

  it("builds one card per indexable page and names it the way each page's og:image points", () => {
    const cards = buildOgCards(options);
    expect(cards.map((c) => c.file)).toEqual(listIndexablePaths().map(ogFileName));
    for (const page of buildPages(options)) expect(page.head).toContain(`https://example.test/og/${ogFileName(page.path)}`);
  });
});
