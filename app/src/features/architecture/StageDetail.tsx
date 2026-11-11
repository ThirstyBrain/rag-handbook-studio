import { useMemo, useState } from "react";
import { findAdr, findChapter, getHandbook } from "@/content/handbook";
import { firstSentence } from "@/content/parse/text";
import { MarkdownBody } from "@/shared/markdown/MarkdownBody";
import { renderMarkdown } from "@/shared/markdown/render";
import { Link } from "@/shared/router/router";
import { Empty } from "@/shared/ui/States";
import { LANE_LABEL, type Stage } from "./stages";

export function StageDetail({ stage }: { stage: Stage }) {
  const hb = getHandbook();
  const chapters = stage.chapters.map((n) => findChapter(n)).filter((c) => c !== undefined);
  const planned = stage.chapters.filter((n) => !findChapter(n)).map((n) => hb.entries.find((e) => e.number === n)).filter((e) => e !== undefined);
  const adrs = stage.adrs.map(findAdr).filter((a) => a !== undefined);
  const diagrams = stage.diagrams.map((f) => hb.diagrams.get(f)).filter((d) => d !== undefined);
  const terms = hb.glossary
    .filter((t) => t.chapters.some((n) => stage.chapters.includes(n)))
    .filter((t, i, all) => all.findIndex((x) => x.term.toLowerCase() === t.term.toLowerCase()) === i)
    .slice(0, 10);
  const [diagramIndex, setDiagramIndex] = useState(0);
  const primary = chapters[0];

  const diagram = diagrams[Math.min(diagramIndex, diagrams.length - 1)];
  const rendered = useMemo(() => (diagram ? renderMarkdown("```mermaid\n" + diagram.source.trim() + "\n```\n") : null), [diagram]);

  return (
    <section id="stage-detail" className="stage" aria-labelledby="stage-title" aria-live="polite">
      <div className="stage__info">
        <p className="stage__lane">{LANE_LABEL[stage.lane]}</p>
        <h2 id="stage-title" className="stage__title">
          {stage.name}
        </h2>
        {primary ? (
          <p className="stage__desc">
            {firstSentence(primary.problem)} <span className="stage__from">From chapter {primary.number}.</span>
          </p>
        ) : (
          <p className="stage__desc">The handbook has not reached this stage yet. It is covered by planned chapters, listed below.</p>
        )}

        {chapters.length > 0 && (
          <div className="stage__block">
            <h3 className="stage__h">Read</h3>
            <ul className="stage__chapters">
              {chapters.map((c) => {
                const key = c.sections.filter((s) => s.level === 3 && /\.4\./.test(s.number)).slice(0, 4);
                return (
                  <li key={c.number}>
                    <Link href={`/handbook/${c.slug}`} className="stage__ch">
                      <span className="stage__chn">{c.number}</span> {c.title}
                    </Link>
                    {key.length > 0 && (
                      <ul className="stage__secs">
                        {key.map((s) => (
                          <li key={s.id}>
                            <Link href={`/handbook/${c.slug}#${s.id}`}>
                              {s.number} {s.title}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {planned.length > 0 && (
          <div className="stage__block">
            <h3 className="stage__h">Planned</h3>
            <ul className="stage__planned">
              {planned.map((e) => (
                <li key={e.number}>
                  Chapter {e.number}, {e.title} <span className="status status--pending">Not written</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {adrs.length > 0 && (
          <div className="stage__block">
            <h3 className="stage__h">Governing decisions</h3>
            <ul className="stage__adrs">
              {adrs.map((a) => (
                <li key={a.id}>
                  <Link href={`/decisions/${a.id}`}>
                    <span className="stage__adr-id">{a.id}</span> {a.title}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}

        {terms.length > 0 && (
          <div className="stage__block">
            <h3 className="stage__h">Terms</h3>
            <p className="stage__terms">
              {terms.map((t) => (
                <Link key={t.slug} href={`/glossary#${t.slug}`} className="stage__term">
                  {t.term}
                </Link>
              ))}
            </p>
          </div>
        )}
      </div>

      <div className="stage__diagrams">
        {diagrams.length > 1 && (
          <div className="stage__dtabs" role="tablist" aria-label="Diagrams for this stage">
            {diagrams.map((d, i) => (
              <button key={d.file} type="button" role="tab" aria-selected={i === diagramIndex} className="stage__dtab" onClick={() => setDiagramIndex(i)}>
                {d.file.replace(/^\d+-/, "").replace(/\.mmd$/, "").replace(/-/g, " ")}
              </button>
            ))}
          </div>
        )}
        {rendered && diagram ? (
          <>
            <MarkdownBody key={diagram.file} html={rendered.html} className="stage__diagram" />
            <p className="stage__dsrc">
              Source: <code>docs/assets/diagrams/{diagram.file}</code>
            </p>
          </>
        ) : (
          <Empty title="No diagram for this stage yet">
            <p>The handbook's diagrams for this stage arrive with its planned chapters.</p>
          </Empty>
        )}
      </div>
    </section>
  );
}
