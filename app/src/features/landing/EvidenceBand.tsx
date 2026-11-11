import { getHandbook } from "@/content/handbook";
import { EVIDENCE_LABELS } from "@/content/parse/evidence";
import type { EvidenceKind } from "@/content/types";
import { useReveal } from "@/shared/hooks/useReveal";

const ORDER: EvidenceKind[] = ["E", "X", "S", "V", "I", "A", "N"];

/** Counts every evidence mark across the written chapters; nothing here is typed in by hand. */
export function EvidenceBand() {
  const hb = getHandbook();
  const ref = useReveal<HTMLDivElement>();
  const totals: Partial<Record<EvidenceKind, number>> = {};
  for (const c of hb.chapters) for (const [k, n] of Object.entries(c.evidence)) totals[k as EvidenceKind] = (totals[k as EvidenceKind] ?? 0) + (n ?? 0);
  const sum = ORDER.reduce((s, k) => s + (totals[k] ?? 0), 0);
  const max = Math.max(...ORDER.map((k) => totals[k] ?? 0));

  return (
    <section className="band page" aria-labelledby="evidence-title">
      <div className="band-head">
        <h2 id="evidence-title" className="band-head__title">
          Every claim says where it came from
        </h2>
        <p className="band-head__text">
          The handbook tags each significant statement: a cited source, something executed in the repository, engineering judgement, a vendor's own number, or an assumption. The reader lets you highlight any one kind.
        </p>
      </div>
      <div ref={ref} className="evidence reveal">
        <p className="evidence__total">
          <span className="evidence__num">{sum.toLocaleString()}</span> evidence marks across {hb.chapters.length} chapters
        </p>
        <ul className="evidence__rows">
          {ORDER.filter((k) => totals[k]).map((k) => (
            <li key={k} className="evidence__row">
              <span className={`ev ev--${k.toLowerCase()} evidence__tag`}>{k === "S" ? "S#" : k}</span>
              <span className="evidence__label">{EVIDENCE_LABELS[k]}</span>
              <span className="evidence__bar" aria-hidden="true">
                <span className={`ev-bg--${k.toLowerCase()}`} style={{ width: `${((totals[k] ?? 0) / max) * 100}%` }} />
              </span>
              <span className="evidence__n">{totals[k]}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
