import { getHandbook } from "@/content/handbook";
import { Link } from "@/shared/router/router";
import { LANE_LABEL, STAGES, type Lane } from "@/features/architecture/stages";

const LANES: Lane[] = ["offline", "online", "cross"];

/** A compact, non-interactive strip of the request path; the full map lives at /architecture. */
export function ExploreBand() {
  const hb = getHandbook();
  return (
    <section className="band page" aria-labelledby="explore-title">
      <div className="explore">
        <div className="explore__copy">
          <h2 id="explore-title" className="band-head__title">
            Walk the system stage by stage
          </h2>
          <p className="band-head__text">
            The architecture map follows a document from ingestion to an answer. Each stage opens the handbook's own diagrams, the chapters that explain it, and the decisions that govern it.
          </p>
          <Link href="/architecture" className="btn btn--primary">
            Open the architecture map
          </Link>
        </div>
        <div className="explore__lanes">
          {LANES.map((lane) => (
            <div key={lane} className="explore__lane">
              <p className="explore__lane-label">{LANE_LABEL[lane]}</p>
              <ol className={`explore__strip explore__strip--${lane}`}>
                {STAGES.filter((s) => s.lane === lane).map((s) => {
                  const written = s.chapters.filter((n) => hb.chapters.some((c) => c.number === n));
                  return (
                    <li key={s.id} className={`explore__stage explore__stage--${s.lane}`}>
                      <Link href={`/architecture#${s.id}`}>
                        <span className="explore__name">{s.name}</span>
                        <span className="explore__ch">{written.length ? `Ch. ${written.join(", ")}` : "Planned"}</span>
                      </Link>
                    </li>
                  );
                })}
              </ol>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
