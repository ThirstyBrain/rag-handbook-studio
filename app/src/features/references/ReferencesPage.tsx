import { useMemo, useState } from "react";
import { getHandbook } from "@/content/handbook";
import { Empty } from "@/shared/ui/States";
import "./references.css";

export default function ReferencesPage() {
  const hb = getHandbook();
  const [q, setQ] = useState("");
  const all = useMemo(() => [...hb.references.values()].sort((a, b) => Number(a.id.slice(1)) - Number(b.id.slice(1))), [hb.references]);
  const citedBy = useMemo(() => {
    const m = new Map<string, number[]>();
    for (const c of hb.chapters) for (const id of new Set(c.markdown.match(/\bS\d+\b/g) ?? [])) m.set(id, [...(m.get(id) ?? []), c.number]);
    return m;
  }, [hb.chapters]);
  const needle = q.trim().toLowerCase();
  const list = needle ? all.filter((r) => r.id.toLowerCase() === needle || r.citation.toLowerCase().includes(needle)) : all;

  return (
    <div className="page refs">
      <header className="page-head">
        <p className="page-head__eyebrow">Sources</p>
        <h1 className="page-head__title">References</h1>
        <p className="page-head__lede">{all.length} reviewed sources behind the [S#] marks in the chapters. The review status says how much of each source the authors actually read.</p>
      </header>
      <input className="field refs__search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by id, author, title or site" aria-label="Filter references" />
      {list.length === 0 ? (
        <Empty title="No source matches that filter" />
      ) : (
        <ol className="refs__list">
          {list.map((r) => (
            <li key={r.id} id={r.id} className="refs__item">
              <span className="refs__id">{r.id}</span>
              <div>
                <p className="refs__cite">{r.citation.replace(/\s*https?:\/\/\S+/g, "")}</p>
                <p className="refs__meta">
                  {r.url && (
                    <a href={r.url} target="_blank" rel="noopener noreferrer">
                      {new URL(r.url).hostname.replace(/^www\./, "")}
                    </a>
                  )}
                  {r.status && <span>Reviewed: {r.status}</span>}
                  {citedBy.get(r.id) && <span>Cited in chapter {citedBy.get(r.id)!.join(", ")}</span>}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
