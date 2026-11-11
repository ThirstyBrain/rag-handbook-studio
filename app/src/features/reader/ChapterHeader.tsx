import { getHandbook } from "@/content/handbook";
import { EVIDENCE_LABELS, EVIDENCE_SHORT } from "@/content/parse/evidence";
import type { Chapter, EvidenceKind } from "@/content/types";
import { Link } from "@/shared/router/router";
import { firstSentence } from "@/content/parse/text";

const ORDER: EvidenceKind[] = ["X", "S", "E", "V", "I", "A", "N"];

export function ChapterHeader({ chapter }: { chapter: Chapter }) {
  const part = getHandbook().parts.find((p) => p.id === chapter.partId);
  const total = ORDER.reduce((s, k) => s + (chapter.evidence[k] ?? 0), 0);

  return (
    <header className="ch-head">
      <p className="ch-head__crumbs">
        <Link href="/handbook">Handbook</Link>
        {part && (
          <>
            <span aria-hidden="true">/</span>
            <Link href={`/handbook#${part.id}`}>
              Part {part.roman}: {part.title}
            </Link>
          </>
        )}
      </p>
      <div className="ch-head__titlewrap">
        <span className="ch-head__num" aria-hidden="true">
          {String(chapter.number).padStart(2, "0")}
        </span>
        <h1 id="chapter-title" className="ch-head__title">
          <span className="visually-hidden">Chapter {chapter.number}: </span>
          {chapter.title}
        </h1>
      </div>
      {chapter.status !== "complete" && (
        <p className="ch-head__wip" role="note">
          Still being written. The handbook marks this chapter as {chapter.status.replace("-", " ")}
          {chapter.statusNote ? `: ${chapter.statusNote}` : ""}. Expect it to change.
        </p>
      )}
      {chapter.problem && <p className="ch-head__lede">{firstSentence(chapter.problem)}</p>}

      <dl className="ch-head__facts">
        <div>
          <dt>Reading time</dt>
          <dd>{chapter.readingMinutes} min</dd>
        </div>
        <div>
          <dt>Sections</dt>
          <dd>{chapter.sections.filter((s) => s.level === 2).length}</dd>
        </div>
        <div>
          <dt>Diagrams</dt>
          <dd>{(chapter.markdown.match(/```mermaid/g) ?? []).length}</dd>
        </div>
        <div>
          <dt>Runnable exercises</dt>
          <dd>{chapter.exercises.length}</dd>
        </div>
      </dl>

      {total > 0 && (
        <div className="evidence-bar" aria-label="Evidence marks in this chapter">
          <div className="evidence-bar__track" aria-hidden="true">
            {ORDER.filter((k) => chapter.evidence[k]).map((k) => (
              <span key={k} className={`evidence-bar__seg ev-bg--${k.toLowerCase()}`} style={{ flexGrow: chapter.evidence[k] }} />
            ))}
          </div>
          <ul className="evidence-bar__legend">
            {ORDER.filter((k) => chapter.evidence[k]).map((k) => (
              <li key={k} title={EVIDENCE_LABELS[k]}>
                <span className={`evidence-bar__dot ev-bg--${k.toLowerCase()}`} aria-hidden="true" />
                {EVIDENCE_SHORT[k]} <span className="evidence-bar__n">{chapter.evidence[k]}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

    </header>
  );
}
