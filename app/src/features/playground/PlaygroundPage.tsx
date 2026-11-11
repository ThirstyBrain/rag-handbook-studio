import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { chapterHrefByNumber } from "@/content/handbook";
import { track } from "@/shared/analytics/track";
import { Link } from "@/shared/router/router";
import { CORPUS, QRELS, SOURCE_FILE } from "./domain/corpus";
import { DEFAULT_SETTINGS, runHybrid, type HybridSettings, type Method } from "./domain/hybrid";
import { FusionDiagram } from "./FusionDiagram";
import { ResultTable } from "./ResultTable";
import { Controls } from "./Controls";
import "./playground.css";

const PRESETS = Object.keys(QRELS);

const METHODS: { id: Method; label: string; explain: string }[] = [
  { id: "bm25", label: "Keyword (BM25)", explain: "Scores documents by the query terms they contain: rare terms count more, repeated terms saturate, long documents are normalised." },
  { id: "dense", label: "Semantic stand-in", explain: "Cosine similarity of character-trigram vectors. It rewards shared spelling, which is why it matches “contractor” to “Contractors”; it understands nothing." },
  { id: "rrf", label: "Hybrid, RRF", explain: "Adds 1 / (k + rank) from each leg. It ignores raw scores entirely, so the two legs' incompatible scales never need calibrating." },
  { id: "minmax", label: "Hybrid, min–max", explain: "Rescales each leg's scores to 0–1 and adds them. It keeps magnitude, so one extreme score can compress all the others." },
];

export default function PlaygroundPage() {
  const [query, setQuery] = useState("contractor leave");
  const [settings, setSettings] = useState<HybridSettings>(DEFAULT_SETTINGS);
  const deferredQuery = useDeferredValue(query);
  const result = useMemo(() => runHybrid(deferredQuery.trim(), settings), [deferredQuery, settings]);
  const changed = JSON.stringify(settings) !== JSON.stringify(DEFAULT_SETTINGS);

  useEffect(() => {
    if (!deferredQuery.trim()) return;
    const t = window.setTimeout(() => track({ name: "playground_query", query: deferredQuery, preset: PRESETS.includes(deferredQuery) }), 800);
    return () => window.clearTimeout(t);
  }, [deferredQuery]);

  const ch9 = chapterHrefByNumber(9);

  return (
    <div className="page lab">
      <header className="page-head">
        <p className="page-head__eyebrow">Experiment</p>
        <h1 className="page-head__title">Retrieval lab</h1>
        <p className="page-head__lede">
          Run a query through a keyword leg and a semantic leg, then watch two fusion methods combine them. This is the toy pipeline from Chapter 9's exercise, ported to run in your browser: eight documents, four judged queries, no network.
        </p>
      </header>

      <div className="lab__grid">
        <div className="lab__main">
          <div className="lab__query">
            <label htmlFor="lab-q" className="lab__qlabel">
              Query
            </label>
            <input id="lab-q" className="field lab__input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Type a question or an identifier, such as E-4471" autoComplete="off" spellCheck={false} />
            <div className="lab__presets" role="group" aria-label="Judged queries from the exercise">
              {PRESETS.map((q) => (
                <button key={q} type="button" className="chip" aria-pressed={q === query} onClick={() => setQuery(q)}>
                  {q}
                </button>
              ))}
            </div>
            {result.queryTokens.length > 0 && (
              <p className="lab__tokens">
                Tokens after analysis:{" "}
                {result.queryTokens.map((t) => (
                  <code key={t}>{t}</code>
                ))}
                <span className="lab__tokens-note">Lower-cased, split on non-alphanumerics, no stemming, as in the script.</span>
              </p>
            )}
          </div>

          {!query.trim() ? (
            <div className="empty lab__empty">
              <p className="empty__title">Type a query to run the pipeline</p>
              <p>Or pick one of the four judged queries above to see nDCG@3 for every method.</p>
            </div>
          ) : (
            <>
              <section className="lab__panel" aria-labelledby="lab-flow">
                <div className="lab__panel-head">
                  <h2 id="lab-flow">How the legs fuse</h2>
                  <p>Lines connect each leg's top three to their place in the fused ranking.</p>
                </div>
                <FusionDiagram result={result} k={settings.k} idPrefix="lab" />
              </section>

              {result.qrels ? (
                <section className="lab__panel" aria-labelledby="lab-metrics">
                  <div className="lab__panel-head">
                    <h2 id="lab-metrics">Quality against the exercise's judgements</h2>
                    <p>nDCG@3 with graded relevance. {changed ? "Your settings differ from the script, so these numbers will not match its printed output." : "With default settings these match the script's printed output exactly."}</p>
                  </div>
                  <div className="lab__metrics">
                    {METHODS.map((m) => {
                      const v = result.ndcg[m.id] ?? 0;
                      const best = Math.max(...METHODS.map((x) => result.ndcg[x.id] ?? 0));
                      return (
                        <div key={m.id} className="metric" data-best={v === best || undefined}>
                          <p className="metric__label">{m.label}</p>
                          <p className="metric__value">{v.toFixed(2)}</p>
                          <span className="metric__bar" aria-hidden="true">
                            <span style={{ width: `${v * 100}%` }} />
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ) : (
                <p className="lab__nojudge">This query has no relevance judgements in the exercise, so no quality metric is shown. Rankings are still computed live.</p>
              )}

              <section className="lab__panel" aria-labelledby="lab-results">
                <div className="lab__panel-head">
                  <h2 id="lab-results">Every ranking, with its scores</h2>
                </div>
                <div className="lab__tables">
                  {METHODS.map((m) => (
                    <ResultTable key={m.id} method={m.id} label={m.label} explain={m.explain} result={result} />
                  ))}
                </div>
              </section>
            </>
          )}
        </div>

        <aside className="lab__side">
          <Controls settings={settings} onChange={setSettings} onReset={() => setSettings(DEFAULT_SETTINGS)} changed={changed} />
          <div className="lab__corpus">
            <h2 className="lab__side-h">The corpus</h2>
            <ol>
              {Object.entries(CORPUS).map(([id, text]) => (
                <li key={id}>
                  <span className="lab__cid">{id}</span> {text}
                </li>
              ))}
            </ol>
          </div>
          <div className="lab__honesty">
            <h2 className="lab__side-h">What this is, and is not</h2>
            <p>
              A deterministic port of <code>{SOURCE_FILE}</code> Part C, checked by a unit test against the script's real output. With eight documents it shows the mechanics of fusion. It says nothing about which method wins on real data; the handbook's advice is to measure on your own golden set, per query class.
            </p>
            <p className="lab__links">
              {ch9 && <Link href={ch9}>Read Chapter 9, Hybrid Search</Link>}
              <Link href="/exercises#ch09_hybrid_search">See the script and its output</Link>
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}
