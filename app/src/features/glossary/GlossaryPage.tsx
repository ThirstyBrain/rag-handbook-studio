import { useMemo, useState } from "react";
import { chapterHrefByNumber, getHandbook } from "@/content/handbook";
import { toPlainText } from "@/content/parse/text";
import { track } from "@/shared/analytics/track";
import { Link } from "@/shared/router/router";
import { Empty } from "@/shared/ui/States";
import { relatedTerms } from "./related";
import "./glossary.css";

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

export default function GlossaryPage() {
  const hb = getHandbook();
  const [q, setQ] = useState("");
  const [letter, setLetter] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return hb.glossary.filter((t) => (!needle || t.term.toLowerCase().includes(needle) || t.definition.toLowerCase().includes(needle)) && (!letter || t.term[0]?.toUpperCase() === letter));
  }, [hb.glossary, q, letter]);

  const present = new Set(hb.glossary.map((t) => t.term[0]?.toUpperCase()));
  const groups = useMemo(() => {
    const m = new Map<string, typeof filtered>();
    for (const t of filtered) {
      const k = /[A-Z]/.test(t.term[0]?.toUpperCase() ?? "") ? t.term[0]!.toUpperCase() : "#";
      m.set(k, [...(m.get(k) ?? []), t]);
    }
    return [...m.entries()];
  }, [filtered]);

  return (
    <div className="page gl">
      <header className="page-head">
        <p className="page-head__eyebrow">Vocabulary</p>
        <h1 className="page-head__title">Glossary</h1>
        <p className="page-head__lede">{hb.glossary.length} terms defined across the written chapters. Each links back to where it is explained and to related terms that appear in its definition.</p>
      </header>

      <div className="gl__tools">
        <input className="field gl__search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter terms and definitions" aria-label="Filter glossary" />
        <div className="gl__alpha" role="group" aria-label="Filter by first letter">
          <button type="button" className="gl__letter" aria-pressed={letter === null} onClick={() => setLetter(null)}>
            All
          </button>
          {ALPHABET.map((L) => (
            <button
              key={L}
              type="button"
              className="gl__letter"
              aria-pressed={letter === L}
              disabled={!present.has(L)}
              onClick={() => {
                setLetter(letter === L ? null : L);
                track({ name: "glossary_filter", letter: L });
              }}
            >
              {L}
            </button>
          ))}
        </div>
        <p className="gl__count" aria-live="polite">
          {filtered.length === hb.glossary.length ? `${filtered.length} terms` : `${filtered.length} of ${hb.glossary.length} terms`}
        </p>
      </div>

      {filtered.length === 0 ? (
        <Empty title="No term matches">
          <p>Clear the filter, or search the whole handbook with Ctrl K; the term may be explained in a chapter without a glossary entry.</p>
        </Empty>
      ) : (
        groups.map(([L, terms]) => (
          <section key={L} className="gl__group" aria-labelledby={`gl-${L}`}>
            <h2 id={`gl-${L}`} className="gl__L">
              {L}
            </h2>
            <dl className="gl__list">
              {terms.map((t) => {
                const rel = relatedTerms(t, hb.glossary);
                return (
                  <div key={t.slug} id={t.slug} className="gl__entry">
                    <dt className="gl__term">{t.term}</dt>
                    <dd className="gl__def">
                      <p>{toPlainText(t.definition)}</p>
                      {(t.chapters.length > 0 || rel.length > 0) && (
                        <p className="gl__links">
                          {t.chapters.map((n) => {
                            const href = chapterHrefByNumber(n);
                            return href ? (
                              <Link key={n} href={href} className="gl__ch">
                                Chapter {n}
                              </Link>
                            ) : null;
                          })}
                          {rel.map((r) => (
                            <a key={r.slug} href={`#${r.slug}`} className="gl__rel">
                              {r.term}
                            </a>
                          ))}
                        </p>
                      )}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </section>
        ))
      )}
    </div>
  );
}
