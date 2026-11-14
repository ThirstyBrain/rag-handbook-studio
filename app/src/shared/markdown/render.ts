import DOMPurify from "dompurify";
import { Marked, Renderer, type Token, type Tokens } from "marked";
import { EVIDENCE_LABELS, EVIDENCE_SHORT, parseEvidenceTag } from "@/content/parse/evidence";
import { slugify } from "@/content/parse/text";
import { escapeHtml, highlight, LANGUAGE_LABELS } from "./highlight";

/**
 * Renders handbook Markdown to sanitised HTML with the handbook's own conventions made interactive:
 *  - evidence tags ([X], [E, S76]) become labelled marks; source ids link to the reference list
 *  - "ADR-004" and "Chapter 6" become links when the target exists
 *  - ```mermaid blocks become diagram figures (rendered lazily by <MarkdownBody>)
 *  - `python -I docs/exercises/x.py` run blocks become exercise-panel slots
 *  - code blocks are highlighted and get a copy button; tables get a scroll container
 */
export interface RenderContext {
  /** Chapter numbers that have a written page. */
  chapterSlugs?: Map<number, string>;
  /** ADR ids that exist, e.g. "ADR-004". */
  adrIds?: Set<string>;
  /** Exercise files that exist. */
  exercises?: Set<string>;
  /** Skip H1 (the page renders its own title). */
  skipH1?: boolean;
}

export interface RenderResult {
  html: string;
  /** Exercise slots in document order: file + args. */
  exerciseSlots: { file: string; args: string }[];
}

const RUN_LINE = /^python3?\s+(?:-I\s+)?(?:docs\/exercises\/)?(ch\d+_[a-z0-9_]+\.py)((?:\s+--[a-z-]+)*)\s*$/;

export function renderMarkdown(md: string, ctx: RenderContext = {}): RenderResult {
  const slots: RenderResult["exerciseSlots"] = [];
  const usedIds = new Map<string, number>();
  const usedSlotIds = new Set<string>();
  const targets = planExercisePlacement(md, ctx.exercises);
  const placedRaw = new Set<string>();

  const slot = (file: string, args: string) => {
    slots.push({ file, args });
    // The first panel for a file owns the plain anchor that inline mentions link to.
    let id = `exercise-${file.replace(/\.py$/, "")}`;
    if (usedSlotIds.has(id)) id += `-${slugify(args) || slots.length}`;
    usedSlotIds.add(id);
    return `<div class="exercise-slot" data-exercise="${escapeHtml(file)}" data-args="${escapeHtml(args)}" id="${escapeHtml(id)}"></div>`;
  };
  /** Panels for exercises cited in prose (never in a run block) go after the chosen top-level block. */
  const placeAfter = (raw: string) => {
    const list = targets.get(raw);
    if (!list || placedRaw.has(raw)) return "";
    placedRaw.add(raw);
    return list.map((t) => slot(t.file, t.args)).join("\n");
  };
  const base = new Renderer();

  const marked = new Marked({ gfm: true });

  marked.use({
    extensions: [
      {
        name: "evidence",
        level: "inline",
        start: (src: string) => src.indexOf("["),
        tokenizer(src: string) {
          const m = /^\[((?:S\d+|[EAIXVN])(?:\s*,\s*(?:S\d+|[EAIXVN]))*)\](?!\()/.exec(src);
          return m ? { type: "evidence", raw: m[0], inner: m[1] } : undefined;
        },
        renderer(token) {
          const parts = parseEvidenceTag(token.inner as string).map((t) =>
            t.kind === "S"
              ? `<a class="ev ev--s" href="#source-${t.ref}" data-source="${t.ref}">${t.ref}</a>`
              : `<abbr class="ev ev--${t.kind.toLowerCase()}" data-kind="${t.kind}" title="${EVIDENCE_LABELS[t.kind]}" aria-label="${EVIDENCE_SHORT[t.kind]}">${t.kind}</abbr>`,
          );
          return `<span class="ev-group">${parts.join("")}</span>`;
        },
      },
      {
        name: "crossref",
        level: "inline",
        start(src: string) {
          const m = /ADR-\d{3}|Chapters?\s+\d/.exec(src);
          return m ? m.index : undefined;
        },
        tokenizer(src: string) {
          const adr = /^ADR-\d{3}/.exec(src);
          if (adr && ctx.adrIds?.has(adr[0])) return { type: "crossref", raw: adr[0], href: `/decisions/${adr[0]}`, label: adr[0] };
          const ch = /^Chapter\s+(\d{1,2})\b/.exec(src);
          if (ch) {
            const slug = ctx.chapterSlugs?.get(Number(ch[1]));
            if (slug) return { type: "crossref", raw: ch[0], href: `/handbook/${slug}`, label: ch[0] };
          }
          return undefined;
        },
        renderer: (token) => `<a class="xref" href="${token.href}">${escapeHtml(token.label as string)}</a>`,
      },
    ],
    renderer: {
      heading({ tokens, depth, text }: Tokens.Heading) {
        if (depth === 1 && ctx.skipH1) return "";
        let id = slugify(text);
        const n = usedIds.get(id) ?? 0;
        usedIds.set(id, n + 1);
        if (n > 0) id = `${id}-${n}`;
        // A leading section number ("9.4.1 BM25") becomes a styled index; the text itself is unchanged.
        const inner = this.parser.parseInline(tokens).replace(/^(\d+(?:\.\d+)+|\d+\.)(\s+)/, '<span class="h-num">$1</span>$2');
        const anchor = depth >= 2 && depth <= 3 ? `<a class="h-anchor" href="#${id}" aria-label="Link to this section">#</a>` : "";
        return `<h${depth} id="${id}">${inner}${anchor}</h${depth}>\n`;
      },
      code({ text, lang }: Tokens.Code) {
        const language = (lang ?? "").trim().toLowerCase();
        if (language === "mermaid") {
          return `<figure class="diagram" data-mermaid="${encodeURIComponent(text)}"><pre class="diagram__fallback">${escapeHtml(text)}</pre></figure>\n`;
        }
        // Replace a block only when every line is an exercise run, so no other source line is ever dropped.
        const lines = text.split("\n").filter((l) => l.trim());
        const runs = lines.map((l) => RUN_LINE.exec(l.trim()));
        if (ctx.exercises && lines.length > 0 && runs.every((r) => r && ctx.exercises!.has(r[1]!))) {
          return runs.map((r) => slot(r![1]!, r![2]!.trim())).join("\n");
        }
        const { html, language: resolved } = highlight(text, language);
        const label = LANGUAGE_LABELS[resolved] ?? resolved;
        return `<div class="code" data-lang="${resolved}"><div class="code__bar"><span class="code__lang">${label}</span><button type="button" class="code__copy" data-copy>Copy</button></div><pre><code class="hljs language-${resolved}">${html}</code></pre></div>\n`;
      },
      table(token: Tokens.Table) {
        const cell = (c: Tokens.TableCell, tag: "th" | "td") => {
          const align = c.align ? ` style="text-align:${c.align}"` : "";
          return `<${tag}${align}>${this.parser.parseInline(c.tokens)}</${tag}>`;
        };
        const head = `<tr>${token.header.map((c) => cell(c, "th")).join("")}</tr>`;
        const body = token.rows.map((r) => `<tr>${r.map((c) => cell(c, "td")).join("")}</tr>`).join("");
        return `<div class="table-wrap" tabindex="0" role="region" aria-label="Scrollable table"><table><thead>${head}</thead><tbody>${body}</tbody></table></div>\n` + placeAfter(token.raw);
      },
      blockquote({ tokens, text, raw }: Tokens.Blockquote) {
        const body = this.parser.parse(tokens);
        const kind = /^\s*\*\*Evidence legend/i.test(text) ? "legend" : /^\s*\*\*(Warning|Caution|Security)/i.test(text) ? "warning" : "note";
        return `<aside class="callout callout--${kind}">${body}</aside>\n` + placeAfter(raw);
      },
      link({ href, title, tokens }: Tokens.Link) {
        const inner = this.parser.parseInline(tokens);
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        if (/^https?:/i.test(href)) return `<a href="${escapeHtml(href)}"${t} target="_blank" rel="noopener noreferrer" class="ext">${inner}</a>`;
        const adr = /ADR-(\d{3})/.exec(href);
        if (adr) return `<a href="/decisions/ADR-${adr[1]}"${t}>${inner}</a>`;
        const ch = /chapters\/(\d{2})-[\w-]+\.md(#[\w-]+)?/.exec(href);
        if (ch) {
          const slug = ctx.chapterSlugs?.get(Number(ch[1]));
          if (slug) return `<a href="/handbook/${slug}${ch[2] ?? ""}"${t}>${inner}</a>`;
        }
        if (href.startsWith("#")) return `<a href="${escapeHtml(href)}"${t}>${inner}</a>`;
        return `<span class="repo-link" title="Repository file: ${escapeHtml(href)}">${inner}</span>`;
      },
      image({ href, title, text }: Tokens.Image) {
        // Chapters link figures as "../assets/images/…". Root-absolute keeps them working on any route depth, trailing slash included.
        const src = href.replace(/^(?:\.\.\/)+assets\/images\//, "/assets/images/");
        const t = title ? ` title="${escapeHtml(title)}"` : "";
        return `<img src="${escapeHtml(src)}" alt="${escapeHtml(text)}"${t} loading="lazy" decoding="async">`;
      },
      codespan({ text }: Tokens.Codespan) {
        const ex = /(?:docs\/exercises\/)?(ch\d+_[a-z0-9_]+\.py)/.exec(text);
        if (ex && ctx.exercises?.has(ex[1]!)) {
          return `<a class="code-ref" href="#exercise-${ex[1]!.replace(/\.py$/, "")}" data-exercise-link="${ex[1]}"><code>${text}</code></a>`;
        }
        return `<code>${text}</code>`;
      },
      paragraph({ tokens, raw }: Tokens.Paragraph) {
        return `<p>${this.parser.parseInline(tokens)}</p>\n` + placeAfter(raw);
      },
      list(token: Tokens.List) {
        base.parser = this.parser;
        return base.list(token) + placeAfter(token.raw);
      },
    },
  });

  const html = marked.parse(md, { async: false }) as string;
  const clean = typeof window !== "undefined" ? DOMPurify.sanitize(html, { ADD_ATTR: ["target"] }) : html;
  return { html: clean, exerciseSlots: slots };
}

/**
 * Decide where each exercise panel goes. Exercises with a run block (a bash block whose only lines
 * are `python -I docs/exercises/...`) are rendered in place of that block. Every other exercise the
 * text cites gets one panel after a top-level block that mentions it: preferably the paragraph that
 * reports the run ("Executed:" or "Run:"), otherwise the first mention. A cited variant such as
 * `--mutants` is preselected.
 */
export function planExercisePlacement(md: string, exercises?: Set<string>): Map<string, { file: string; args: string }[]> {
  const targets = new Map<string, { file: string; args: string }[]>();
  if (!exercises?.size) return targets;
  const top: Token[] = new Marked({ gfm: true }).lexer(md);

  const inRunBlock = new Set<string>();
  for (const t of top) {
    if (t.type !== "code") continue;
    const lines = (t as Tokens.Code).text.split("\n").filter((l) => l.trim());
    const runs = lines.map((l) => RUN_LINE.exec(l.trim()));
    if (lines.length && runs.every((r) => r && exercises.has(r[1]!))) runs.forEach((r) => inRunBlock.add(r![1]!));
  }

  const candidates = new Map<string, { raw: string; args: string; preferred: boolean }[]>();
  for (const t of top) {
    if (!["paragraph", "list", "table", "blockquote"].includes(t.type)) continue;
    for (const m of t.raw.matchAll(/(ch\d+_[a-z0-9_]+\.py)((?:\s+--[a-z-]+)*)/g)) {
      const file = m[1]!;
      if (!exercises.has(file) || inRunBlock.has(file)) continue;
      const list = candidates.get(file) ?? [];
      list.push({ raw: t.raw, args: m[2]!.trim(), preferred: t.type === "paragraph" && /^\s*(Executed|Run):/.test(t.raw) });
      candidates.set(file, list);
    }
  }

  for (const [file, list] of candidates) {
    const chosen = list.find((c) => c.preferred) ?? list[0]!;
    const args = chosen.args || list.find((c) => c.args)?.args || "";
    targets.set(chosen.raw, [...(targets.get(chosen.raw) ?? []), { file, args }]);
  }
  return targets;
}
