import { getHandbook } from "@/content/handbook";
import { useReveal } from "@/shared/hooks/useReveal";
import { Link } from "@/shared/router/router";
import { firstSentence } from "@/content/parse/text";

/** The written parts as a reading path: each part is a stage, each chapter a stop. */
export function ReadingPath() {
  const hb = getHandbook();
  const ref = useReveal<HTMLDivElement>();
  const writtenParts = hb.parts.filter((p) => hb.chapters.some((c) => c.partId === p.id));
  const plannedParts = hb.parts.filter((p) => !hb.chapters.some((c) => c.partId === p.id));

  return (
    <section className="band page" aria-labelledby="path-title">
      <div className="band-head">
        <h2 id="path-title" className="band-head__title">
          Read it in order, or start where your system hurts
        </h2>
        <p className="band-head__text">
          Each chapter follows the same arc: the problem, why it matters in production, the internals, an architecture, an executed example, trade-offs, failure modes and the decision it feeds.
        </p>
      </div>

      <div ref={ref} className="path reveal">
        {writtenParts.map((p) => {
          const chapters = hb.chapters.filter((c) => c.partId === p.id);
          return (
            <div key={p.id} className="path__part">
              <div className="path__part-head">
                <span className="path__roman">Part {p.roman}</span>
                <h3 className="path__part-title">{p.title}</h3>
                <span className="path__count">
                  {chapters.length} chapters, {chapters.reduce((s, c) => s + c.readingMinutes, 0)} min
                </span>
              </div>
              <ol className="path__list">
                {chapters.map((c) => (
                  <li key={c.number}>
                    <Link href={`/handbook/${c.slug}`} className="path__item">
                      <span className="path__n">{c.number}</span>
                      <span className="path__body">
                        <span className="path__title">{c.title}</span>
                        <span className="path__desc">{firstSentence(c.problem)}</span>
                      </span>
                      <span className="path__meta">{c.readingMinutes} min</span>
                    </Link>
                  </li>
                ))}
              </ol>
            </div>
          );
        })}
      </div>

      {plannedParts.length > 0 && (
        <p className="path__planned">
          Still to be written: {plannedParts.map((p) => p.title).join(", ")}.{" "}
          <Link href="/handbook">See the full plan</Link>
        </p>
      )}
    </section>
  );
}
