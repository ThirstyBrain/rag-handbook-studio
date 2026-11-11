import { getHandbook } from "@/content/handbook";
import { Link } from "@/shared/router/router";
import { getCompleted } from "./readingState";

/** Left column: every written chapter grouped by part, current one marked. */
export function ChapterSidebar({ current, onNavigate }: { current: number; onNavigate?: () => void }) {
  const hb = getHandbook();
  const completed = getCompleted();
  const parts = hb.parts.filter((p) => hb.chapters.some((c) => c.partId === p.id));

  return (
    <nav className="ch-side" aria-label="Chapters">
      {parts.map((p) => (
        <div key={p.id} className="ch-side__part">
          <p className="ch-side__part-title">
            <span className="ch-side__roman">{p.roman}</span> {p.title}
          </p>
          <ol className="ch-side__list">
            {hb.chapters
              .filter((c) => c.partId === p.id)
              .map((c) => (
                <li key={c.number}>
                  <Link
                    href={`/handbook/${c.slug}`}
                    className="ch-side__link"
                    aria-current={c.number === current ? "page" : undefined}
                    data-done={completed.has(c.number) || undefined}
                    onClick={onNavigate}
                  >
                    <span className="ch-side__n">{c.number}</span>
                    <span>{c.title}</span>
                  </Link>
                </li>
              ))}
          </ol>
        </div>
      ))}
      <Link href="/handbook" className="ch-side__all" onClick={onNavigate}>
        All {hb.entries.length} chapters, including planned
      </Link>
    </nav>
  );
}
