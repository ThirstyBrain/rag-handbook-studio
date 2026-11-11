import { useMemo, useState } from "react";
import { track } from "@/shared/analytics/track";
import { Link } from "@/shared/router/router";
import { FusionDiagram } from "@/features/playground/FusionDiagram";
import { QRELS } from "@/features/playground/domain/corpus";
import { DEFAULT_SETTINGS, runHybrid } from "@/features/playground/domain/hybrid";
import { useReveal } from "@/shared/hooks/useReveal";

const PRESETS = Object.keys(QRELS);

/** The live two-leg fusion bench: the handbook's ch09 toy pipeline, running in the page. */
export function BenchBand() {
  const [query, setQuery] = useState("contractor leave");
  const result = useMemo(() => runHybrid(query), [query]);
  const ref = useReveal<HTMLDivElement>();

  const pick = (q: string) => {
    setQuery(q);
    track({ name: "playground_query", query: q, preset: true });
  };

  return (
    <section className="band page" aria-labelledby="bench-title">
      <div className="band-head">
        <h2 id="bench-title" className="band-head__title">
          Hybrid retrieval, running in this page
        </h2>
        <p className="band-head__text">
          Pick a question and watch the keyword leg and the semantic leg fuse into one ranking. The lines are the real rank movements computed by the chapter 9 exercise, ported to the browser.
        </p>
      </div>
      <div ref={ref} className="bench reveal">
        <div className="bench__top">
          <div className="bench__presets" role="group" aria-label="Example queries from the handbook exercise">
            {PRESETS.map((q) => (
              <button key={q} type="button" className="chip bench__chip" aria-pressed={q === query} onClick={() => pick(q)}>
                {q}
              </button>
            ))}
          </div>
          {result.qrels && (
            <p className="bench__scores">
              nDCG@3: keyword <b>{result.ndcg.bm25?.toFixed(2)}</b>, semantic <b>{result.ndcg.dense?.toFixed(2)}</b>, fused <b>{result.ndcg.rrf?.toFixed(2)}</b>
            </p>
          )}
        </div>
        <FusionDiagram result={result} k={DEFAULT_SETTINGS.k} idPrefix="bench" />
        <p className="bench__caption">
          Eight documents from <code>ch09_hybrid_search.py</code>. The semantic leg is a character-trigram stand-in, not an embedding model, so this shows mechanics, not quality. <Link href="/lab">Open the retrieval lab</Link>
        </p>
      </div>
    </section>
  );
}
