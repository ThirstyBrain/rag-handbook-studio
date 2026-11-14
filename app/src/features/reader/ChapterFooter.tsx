import { findAdr, getHandbook } from "@/content/handbook";
import type { Chapter } from "@/content/types";
import { Link } from "@/shared/router/router";
import { PUBLISHER, REPO_URL } from "@/seo/siteConfig";
import { relatedChapters } from "./related";

export function ChapterFooter({ chapter, prev, next }: { chapter: Chapter; prev?: Chapter; next?: Chapter }) {
  const hb = getHandbook();
  const related = relatedChapters(chapter, hb.chapters);
  const adrs = chapter.adrs.map(findAdr).filter((a) => a !== undefined);

  return (
    <footer className="ch-foot">
      <nav className="ch-foot__pager" aria-label="Previous and next chapter">
        {prev ? (
          <Link href={`/handbook/${prev.slug}`} className="ch-foot__page ch-foot__page--prev" rel="prev">
            <span className="ch-foot__dir">Previous, chapter {prev.number}</span>
            <span className="ch-foot__t">{prev.title}</span>
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={`/handbook/${next.slug}`} className="ch-foot__page ch-foot__page--next" rel="next">
            <span className="ch-foot__dir">Next, chapter {next.number}</span>
            <span className="ch-foot__t">{next.title}</span>
          </Link>
        ) : (
          <Link href="/handbook" className="ch-foot__page ch-foot__page--next">
            <span className="ch-foot__dir">That is the last written chapter</span>
            <span className="ch-foot__t">See what is planned</span>
          </Link>
        )}
      </nav>

      <div className="ch-foot__grid">
        {related.length > 0 && (
          <section>
            <h2 className="ch-foot__h">Connected chapters</h2>
            <ul className="ch-foot__list">
              {related.map((r) => (
                <li key={r.chapter.number}>
                  <Link href={`/handbook/${r.chapter.slug}`}>
                    <span className="ch-foot__n">{r.chapter.number}</span>
                    {r.chapter.title}
                  </Link>
                  <span className="ch-foot__why">{r.direction === "cites" ? "Referenced here" : r.direction === "cited-by" ? "Builds on this chapter" : "Referenced both ways"}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        {adrs.length > 0 && (
          <section>
            <h2 className="ch-foot__h">Decisions this chapter informs</h2>
            <ul className="ch-foot__list">
              {adrs.map((a) => (
                <li key={a.id}>
                  <Link href={`/decisions/${a.id}`}>
                    <span className="ch-foot__n ch-foot__n--adr">{a.id.replace("ADR-", "")}</span>
                    {a.title}
                  </Link>
                  <span className={`status status--${a.status.toLowerCase()}`}>{a.status}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
      <p className="ch-foot__source">
        Written and maintained by{" "}
        <a href={REPO_URL} target="_blank" rel="noopener noreferrer">
          {PUBLISHER.name}
        </a>
        . <Link href="/about">How claims are verified, and how to report an error.</Link>
      </p>
      <p className="ch-foot__source">
        Rendered from <code>{chapter.sourcePath}</code>.{" "}
        {chapter.status === "complete" && chapter.statusNote && <>Marked complete in the handbook, {chapter.statusNote}.</>}
      </p>
    </footer>
  );
}
