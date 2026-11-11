import { useMemo, useState } from "react";
import { getHandbook } from "@/content/handbook";
import { firstSentence } from "@/content/parse/text";
import { Link } from "@/shared/router/router";
import { Empty } from "@/shared/ui/States";
import { getCompleted } from "@/features/reader/readingState";
import "./handbook-index.css";

type Show = "all" | "written" | "planned";

export default function HandbookIndexPage() {
  const hb = getHandbook();
  const [q, setQ] = useState("");
  const [show, setShow] = useState<Show>("all");
  const completed = getCompleted();
  const byNumber = useMemo(() => new Map(hb.chapters.map((c) => [c.number, c])), [hb.chapters]);

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return hb.entries.filter((e) => {
      const c = byNumber.get(e.number);
      if (show === "written" && !c) return false;
      if (show === "planned" && c) return false;
      if (!needle) return true;
      const hay = `${e.title} ${c?.problem ?? ""} ${c?.sections.map((s) => s.title).join(" ") ?? ""}`.toLowerCase();
      return hay.includes(needle);
    });
  }, [hb.entries, byNumber, q, show]);

  const written = hb.chapters.filter((c) => c.status === "complete").length;
  const drafting = hb.chapters.length - written;
  const minutes = hb.chapters.reduce((s, c) => s + c.readingMinutes, 0);

  return (
    <div className="page toc">
      <header className="page-head">
        <p className="page-head__eyebrow">The handbook</p>
        <h1 className="page-head__title">Contents</h1>
        <p className="page-head__lede">
          {hb.entries.length} chapters in {hb.parts.length} parts. {written} are complete{drafting ? ` and ${drafting} in progress` : ""}, about {Math.round(minutes / 60)} hours of reading; the rest are planned in the handbook's table of contents and appear here as they are written.
        </p>
      </header>

      <div className="toc__spine" aria-label={`${written} of ${hb.entries.length} chapters written`}>
        {hb.parts.map((p) => {
          const entries = hb.entries.filter((e) => e.partId === p.id);
          return (
            <a key={p.id} href={`#${p.id}`} className="toc__spine-part" style={{ flexGrow: entries.length }} title={`Part ${p.roman}: ${p.title}`}>
              <span className="toc__spine-cells" aria-hidden="true">
                {entries.map((e) => (
                  <span
                    key={e.number}
                    className="toc__cell"
                    data-written={byNumber.get(e.number)?.status === "complete" || undefined}
                    data-drafting={(byNumber.has(e.number) && byNumber.get(e.number)?.status !== "complete") || undefined}
                    data-read={completed.has(e.number) || undefined}
                  />
                ))}
              </span>
              <span className="toc__spine-label">{p.roman}</span>
            </a>
          );
        })}
      </div>
      <p className="toc__legend">
        <span className="toc__key toc__key--written" /> Complete <span className="toc__key toc__key--drafting" /> In progress <span className="toc__key toc__key--read" /> Read on this device <span className="toc__key" /> Planned
      </p>

      <div className="toc__tools">
        <input className="field" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by title, topic or section" aria-label="Filter chapters" />
        <div className="toc__show" role="group" aria-label="Show chapters">
          {(["all", "written", "planned"] as Show[]).map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={show === s} onClick={() => setShow(s)}>
              {s === "all" ? "All" : s === "written" ? "Written" : "Planned"}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <Empty title="No chapter matches">
          <p>Try a broader word, or use search (Ctrl K) to look inside the chapters' full text.</p>
        </Empty>
      ) : (
        hb.parts.map((p) => {
          const entries = visible.filter((e) => e.partId === p.id);
          if (!entries.length) return null;
          const partWritten = hb.entries.filter((e) => e.partId === p.id && byNumber.has(e.number)).length;
          const partTotal = hb.entries.filter((e) => e.partId === p.id).length;
          return (
            <section key={p.id} id={p.id} className="toc__part" aria-labelledby={`${p.id}-h`}>
              <div className="toc__part-head">
                <p className="toc__roman">Part {p.roman}</p>
                <h2 id={`${p.id}-h`} className="toc__part-title">
                  {p.title}
                </h2>
                <p className="toc__part-meta">
                  {partWritten === partTotal ? `All ${partTotal} written` : partWritten === 0 ? `${partTotal} planned` : `${partWritten} of ${partTotal} written`}
                </p>
              </div>
              <ol className="toc__rows">
                {entries.map((e) => {
                  const c = byNumber.get(e.number);
                  return (
                    <li key={e.number}>
                      {c ? (
                        <Link href={`/handbook/${c.slug}`} className="toc__row">
                          <span className="toc__n">{e.number}</span>
                          <span className="toc__body">
                            <span className="toc__title">{c.title}</span>
                            <span className="toc__desc">{firstSentence(c.problem)}</span>
                          </span>
                          <span className="toc__meta">
                            <span>{c.readingMinutes} min</span>
                            {c.exercises.length > 0 && <span>{c.exercises.length} exercise{c.exercises.length > 1 ? "s" : ""}</span>}
                            {c.status !== "complete" && <span className="status status--proposed">In progress</span>}
                            {completed.has(c.number) && <span className="toc__read">Read</span>}
                          </span>
                        </Link>
                      ) : (
                        <div className="toc__row toc__row--planned" aria-label={`Chapter ${e.number}, ${e.title}, planned`}>
                          <span className="toc__n">{e.number}</span>
                          <span className="toc__body">
                            <span className="toc__title">{e.title}</span>
                          </span>
                          <span className="toc__meta">
                            <span className="status status--pending">Planned</span>
                          </span>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ol>
            </section>
          );
        })
      )}
    </div>
  );
}
