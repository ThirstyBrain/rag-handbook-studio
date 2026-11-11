import { useEffect, useMemo, useRef, useState } from "react";
import { chapterHrefByNumber, findAdr, getHandbook } from "@/content/handbook";
import { handbookRenderContext } from "@/content/renderContext";
import type { Adr, AdrSectionKind } from "@/content/types";
import { MarkdownBody, type SourceAnchor } from "@/shared/markdown/MarkdownBody";
import { renderMarkdown } from "@/shared/markdown/render";
import { Link } from "@/shared/router/router";
import { NotFound } from "@/app/NotFound";
import { SourcePopover } from "@/features/reader/SourcePopover";
import "./decisions.css";

/** The reasoning arc every ADR follows; shown as a navigable strip above the record. */
const ANATOMY: { kind: AdrSectionKind; label: string }[] = [
  { kind: "context", label: "Context" },
  { kind: "options", label: "Options" },
  { kind: "decision", label: "Decision" },
  { kind: "tradeoffs", label: "Trade-offs" },
  { kind: "consequences", label: "Consequences" },
  { kind: "reversal", label: "Reverse if" },
];

export default function DecisionsPage({ params }: { params: Record<string, string> }) {
  const hb = getHandbook();
  const adr = params.id ? findAdr(params.id) : hb.adrs[0];
  const indexRef = useRef<HTMLElement>(null);

  // On narrow screens the index is a horizontal strip: keep the current record visible in it.
  useEffect(() => {
    indexRef.current?.querySelector<HTMLElement>('[aria-current="page"]')?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [adr?.id]);

  if (params.id && !adr) return <NotFound />;

  return (
    <div className="page adrs">
      <header className="page-head">
        <p className="page-head__eyebrow">Decide</p>
        <h1 className="page-head__title">Architecture decisions</h1>
        <p className="page-head__lede">
          {hb.adrs.length} records of what the handbook's reference system will do, what else was considered, and the evidence that would change the decision. Chapters amend them as research lands.
        </p>
      </header>
      <div className="adrs__layout">
        <nav ref={indexRef} className="adrs__index" aria-label="Decision records">
          <ol>
            {hb.adrs.map((a) => (
              <li key={a.id}>
                <Link href={`/decisions/${a.id}`} className="adrs__link" aria-current={a.id === adr?.id ? "page" : undefined}>
                  <span className="adrs__id">{a.id.replace("ADR-", "")}</span>
                  <span className="adrs__name">{a.title}</span>
                  <span className={`status status--${a.status.toLowerCase()}`} aria-label={`Status ${a.status}`} />
                </Link>
              </li>
            ))}
          </ol>
        </nav>
        {adr && <Record key={adr.id} adr={adr} />}
      </div>
    </div>
  );
}

function Record({ adr }: { adr: Adr }) {
  const [source, setSource] = useState<SourceAnchor | null>(null);
  const ctx = handbookRenderContext();
  const sections = useMemo(() => adr.sections.filter((s) => s.kind !== "status").map((s) => ({ ...s, html: renderMarkdown(s.markdown, ctx).html })), [adr, ctx]);
  const amendments = adr.sections.filter((s) => s.kind === "amendment" || s.kind === "verification");
  const present = new Set(adr.sections.map((s) => s.kind));

  const jump = (kind: AdrSectionKind) => {
    const s = adr.sections.find((x) => x.kind === kind);
    if (s) document.getElementById(s.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <article className="adr" aria-labelledby="adr-title">
      <header className="adr__head">
        <p className="adr__id">{adr.id}</p>
        <h2 id="adr-title" className="adr__title">
          {adr.title}
        </h2>
        <p className="adr__status">
          <span className={`status status--${adr.status.toLowerCase()}`}>{adr.status}</span>
          <span className="adr__statusline">{adr.statusLine.replace(/^\w+\s*[—–-]?\s*/, "")}</span>
        </p>
        <ol className="anatomy" aria-label="Jump to part of the decision">
          {ANATOMY.map((a, i) => (
            <li key={a.kind}>
              <button type="button" className="anatomy__step" disabled={!present.has(a.kind)} onClick={() => jump(a.kind)}>
                <span className="anatomy__n">{i + 1}</span>
                {a.label}
              </button>
            </li>
          ))}
        </ol>
        {amendments.length > 0 && (
          <p className="adr__amend">
            Revised {amendments.length} time{amendments.length > 1 ? "s" : ""} since it was proposed:{" "}
            {amendments.map((s, i) => (
              <span key={s.id}>
                {i > 0 && ", "}
                <a href={`#${s.id}`}>{s.title.replace(/^(Amendment|Verification)\s*/, (m) => m.trim().toLowerCase() + " ")}</a>
              </span>
            ))}
          </p>
        )}
      </header>

      <div className="adr__body">
        {sections.map((s) => (
          <section key={s.id} id={s.id} className={`adr-sec adr-sec--${s.kind}`} aria-labelledby={`${s.id}-h`}>
            <h3 id={`${s.id}-h`} className="adr-sec__title">
              {s.title}
            </h3>
            <MarkdownBody html={s.html} onSource={setSource} />
          </section>
        ))}
      </div>

      {adr.chapters.length > 0 && (
        <footer className="adr__foot">
          <h3 className="adr-sec__title">Discussed in</h3>
          <ul>
            {adr.chapters.map((n) => {
              const href = chapterHrefByNumber(n);
              const c = getHandbook().chapters.find((x) => x.number === n);
              return href && c ? (
                <li key={n}>
                  <Link href={href}>
                    Chapter {n}, {c.title}
                  </Link>
                </li>
              ) : null;
            })}
          </ul>
          <p className="adr__src">
            Rendered from <code>{adr.sourcePath}</code>.
          </p>
        </footer>
      )}
      {source && <SourcePopover anchor={source} onClose={() => setSource(null)} />}
    </article>
  );
}
