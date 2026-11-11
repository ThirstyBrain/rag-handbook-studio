import { CORPUS } from "./domain/corpus";
import type { HybridResult, Method } from "./domain/hybrid";

const TONE: Record<Method, string> = { bm25: "lex", dense: "den", rrf: "fused", minmax: "fused" };

export function ResultTable({ method, label, explain, result }: { method: Method; label: string; explain: string; result: HybridResult }) {
  const rows = method === "bm25" ? result.lexical : method === "dense" ? result.dense : method === "rrf" ? result.rrf : result.minmax;
  const max = Math.max(...rows.map((r) => r.score), 1e-9);
  const rel = result.qrels ?? {};

  return (
    <div className={`rt rt--${TONE[method]}`}>
      <h3 className="rt__title">{label}</h3>
      <p className="rt__explain">{explain}</p>
      {rows.length === 0 ? (
        <p className="rt__empty">No document scored above zero.</p>
      ) : (
        <table className="rt__table">
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Document</th>
              <th scope="col" className="rt__num">
                Score
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 5).map((r) => {
              const terms = method === "bm25" ? result.lexical.find((l) => l.id === r.id)?.terms : undefined;
              return (
                <tr key={r.id} data-rel={rel[r.id] ?? 0}>
                  <td className="rt__rank">{r.rank}</td>
                  <td>
                    <span className="rt__doc">
                      <span className="rt__id">{r.id}</span>
                      {rel[r.id] ? <span className="rt__rel">{rel[r.id] === 2 ? "relevant" : "partial"}</span> : null}
                    </span>
                    <span className="rt__text">{CORPUS[r.id]}</span>
                    {terms && terms.length > 0 && (
                      <span className="rt__terms">
                        {terms.map((t) => (
                          <span key={t.term} title={`tf ${t.tf}, idf ${t.idf.toFixed(3)}`}>
                            <code>{t.term}</code> +{t.score.toFixed(3)}
                          </span>
                        ))}
                      </span>
                    )}
                  </td>
                  <td className="rt__num">
                    <span className="rt__score">{r.score.toFixed(4)}</span>
                    <span className="rt__bar" aria-hidden="true">
                      <span style={{ width: `${(r.score / max) * 100}%` }} />
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
