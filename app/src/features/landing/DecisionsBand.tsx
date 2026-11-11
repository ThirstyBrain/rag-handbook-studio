import { getHandbook } from "@/content/handbook";
import { useReveal } from "@/shared/hooks/useReveal";
import { Link } from "@/shared/router/router";

export function DecisionsBand() {
  const hb = getHandbook();
  const ref = useReveal<HTMLOListElement>();
  return (
    <section className="band page" aria-labelledby="adr-title">
      <div className="band-head">
        <h2 id="adr-title" className="band-head__title">
          Decisions, with the conditions that would reverse them
        </h2>
        <p className="band-head__text">
          The chapters feed {hb.adrs.length} architecture decision records. Each one states its options, trade-offs and consequences, and is amended as later chapters add evidence.
        </p>
      </div>
      <ol ref={ref} className="ledger reveal">
        {hb.adrs.map((a) => (
          <li key={a.id}>
            <Link href={`/decisions/${a.id}`} className="ledger__row">
              <span className="ledger__id">{a.id}</span>
              <span className="ledger__title">{a.title}</span>
              <span className="ledger__chapters">{a.chapters.length ? `Chapters ${a.chapters.join(", ")}` : ""}</span>
              <span className={`status status--${a.status.toLowerCase()}`}>{a.status}</span>
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}
