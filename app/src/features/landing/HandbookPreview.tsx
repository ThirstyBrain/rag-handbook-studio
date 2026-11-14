import { useMemo } from "react";
import { findExercise } from "@/content/handbook";
import { highlight } from "@/shared/markdown/highlight";
import { Link } from "@/shared/router/router";
import { BrandMark } from "@/shared/ui/BrandMark";
import { Icon } from "@/shared/ui/Icon";
import { CORPUS, SOURCE_FILE } from "@/features/playground/domain/corpus";
import { runHybrid } from "@/features/playground/domain/hybrid";

const QUERY = "contractor leave";

/** The first lines of the real `rrf` function from the chapter 9 exercise (falls back to nothing). */
function rrfExcerpt(): string {
  const src = findExercise(SOURCE_FILE)?.source ?? "";
  const start = src.indexOf("def rrf(");
  if (start < 0) return "";
  return src.slice(start).split("\n").slice(0, 6).join("\n");
}

/**
 * A layered preview of the reading interface: the hybrid-retrieval page, its real code, and the
 * live fused ranking for one judged query from the exercise. Decorative frame, real content.
 */
export function HandbookPreview() {
  const result = useMemo(() => runHybrid(QUERY), []);
  const code = useMemo(() => highlight(rrfExcerpt(), "python").html, []);
  const top = result.rrf.slice(0, 3);
  const max = top[0]?.score ?? 1;

  return (
    <figure className="preview" aria-label="Preview of the handbook's hybrid retrieval page">
      <div className="preview__card">
        <div className="preview__bar" aria-hidden="true">
          <span className="preview__brand">
            <BrandMark size={20} />
            <b>RAG Architecture</b> Handbook
          </span>
          <span className="preview__links">
            <span>Handbook</span>
            <span>Architecture</span>
            <span>Decisions</span>
            <span>Glossary</span>
          </span>
          <span className="preview__search">
            <Icon name="search" size={12} /> Search…
          </span>
        </div>

        <div className="preview__body">
          <div className="preview__copy">
            <p className="preview__kicker">Chapter 9</p>
            <p className="preview__title">Hybrid Retrieval Running in This Page</p>
            <p className="preview__text">Dense retrieval matches meaning; lexical retrieval matches terms. Reciprocal rank fusion combines both rankings without comparing their scores.</p>
            {code && (
              <pre className="preview__code" aria-label={`Excerpt of rrf() from ${SOURCE_FILE}`}>
                <code className="hljs language-python" dangerouslySetInnerHTML={{ __html: code }} />
              </pre>
            )}
            <Link href="/lab" className="preview__more">
              Open the lab <Icon name="arrowRight" size={14} />
            </Link>
          </div>

          <div className="preview__viz" aria-label={`Live fused ranking for “${QUERY}”`}>
            <p className="preview__q">
              <Icon name="search" size={13} /> {QUERY}
            </p>
            <ol className="preview__docs">
              {top.map((d, i) => (
                <li key={d.id} className="preview__doc" style={{ "--i": i } as React.CSSProperties}>
                  <span className="preview__doc-id">{d.id}</span>
                  <span className="preview__doc-text">{CORPUS[d.id]}</span>
                  <span className="preview__doc-bar">
                    <span style={{ width: `${(d.score / max) * 100}%` }} />
                  </span>
                  <span className="preview__doc-score">{d.score.toFixed(4)}</span>
                </li>
              ))}
            </ol>
            <div className="preview__lens" aria-hidden="true">
              <Icon name="search" size={34} strokeWidth={2} />
            </div>
            <div className="preview__platform" aria-hidden="true" />
          </div>
        </div>
      </div>
    </figure>
  );
}
