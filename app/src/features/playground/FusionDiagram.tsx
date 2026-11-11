import { CORPUS } from "./domain/corpus";
import type { HybridResult, RankedDoc } from "./domain/hybrid";
import "./fusion-diagram.css";

/**
 * The two retrieval legs feeding one fused ranking, drawn as an architecture diagram whose
 * connectors are the actual rank movements. Geometry is fixed-row so connectors can be computed.
 */
const ROW = 44;
const HEAD = 30;
const GAP = 22;
const LEG_ROWS = 3;
const FUSED_ROWS = 5;

const legHeight = HEAD + LEG_ROWS * ROW;
const totalHeight = legHeight * 2 + GAP;
const fusedTop = (totalHeight - (HEAD + FUSED_ROWS * ROW)) / 2;

const rowY = (blockTop: number, i: number) => blockTop + HEAD + i * ROW + ROW / 2;

export function FusionDiagram({ result, k, idPrefix = "fd" }: { result: HybridResult; k: number; idPrefix?: string }) {
  const lex = result.lexical.slice(0, LEG_ROWS);
  const den = result.dense.slice(0, LEG_ROWS);
  const fused = result.rrf.slice(0, FUSED_ROWS);
  const fusedIndex = new Map(fused.map((d, i) => [d.id, i]));
  const rel = result.qrels ?? {};

  const links = [
    ...lex.map((d, i) => ({ leg: "lex" as const, id: d.id, from: rowY(0, i), to: fusedIndex.has(d.id) ? rowY(fusedTop, fusedIndex.get(d.id)!) : null })),
    ...den.map((d, i) => ({ leg: "den" as const, id: d.id, from: rowY(legHeight + GAP, i), to: fusedIndex.has(d.id) ? rowY(fusedTop, fusedIndex.get(d.id)!) : null })),
  ];

  return (
    <div className="fd" style={{ "--fd-h": `${totalHeight}px`, "--fd-row": `${ROW}px`, "--fd-head": `${HEAD}px`, "--fd-gap": `${GAP}px`, "--fd-fused-top": `${fusedTop}px` } as React.CSSProperties}>
      <div className="fd__legs">
        <Leg title="Keyword leg" detail="BM25" tone="lex" docs={lex} rel={rel} emptyText="No term matches" />
        <Leg title="Semantic leg" detail="trigram stand-in" tone="den" docs={den} rel={rel} emptyText="No similar text" />
      </div>

      <svg className="fd__wires" viewBox={`0 0 100 ${totalHeight}`} preserveAspectRatio="none" aria-hidden="true" key={result.query}>
        {links
          .filter((l) => l.to !== null)
          .map((l, i) => (
            <path
              key={`${l.leg}-${l.id}`}
              className={`fd__wire fd__wire--${l.leg}`}
              d={`M0 ${l.from} C 50 ${l.from}, 50 ${l.to}, 100 ${l.to}`}
              pathLength={1}
              style={{ animationDelay: `${i * 40}ms` }}
              vectorEffect="non-scaling-stroke"
            />
          ))}
      </svg>

      <div className="fd__fused">
        <p className="fd__head fd__head--fused">
          <span>Fused</span>
          <span className="fd__detail">RRF, k = {k}</span>
        </p>
        <ol className="fd__rows" aria-label="Fused ranking">
          {fused.map((d) => (
            <DocRow key={`${result.query}-${d.id}`} doc={d} rel={rel[d.id]} showScore />
          ))}
          {fused.length === 0 && <li className="fd__empty">Neither leg returned anything to fuse.</li>}
        </ol>
      </div>
      <span className="visually-hidden" id={`${idPrefix}-desc`}>
        Lexical top three: {lex.map((d) => d.id).join(", ") || "none"}. Semantic top three: {den.map((d) => d.id).join(", ") || "none"}. Fused ranking: {fused.map((d) => d.id).join(", ")}.
      </span>
    </div>
  );
}

function Leg({ title, detail, tone, docs, rel, emptyText }: { title: string; detail: string; tone: "lex" | "den"; docs: RankedDoc[]; rel: Record<string, number>; emptyText: string }) {
  return (
    <div className={`fd__leg fd__leg--${tone}`}>
      <p className="fd__head">
        <span>{title}</span>
        <span className="fd__detail">{detail}</span>
      </p>
      <ol className="fd__rows" aria-label={`${title} ranking`}>
        {docs.map((d) => (
          <DocRow key={d.id} doc={d} rel={rel[d.id]} />
        ))}
        {docs.length === 0 && <li className="fd__empty">{emptyText}</li>}
      </ol>
    </div>
  );
}

function DocRow({ doc, rel, showScore }: { doc: RankedDoc; rel?: number; showScore?: boolean }) {
  return (
    <li className="fd__row" data-rel={rel ?? 0}>
      <span className="fd__rank">{doc.rank}</span>
      <span className="fd__doc">
        <span className="fd__id">{doc.id}</span>
        <span className="fd__text">{CORPUS[doc.id]}</span>
      </span>
      {showScore && <span className="fd__score">{doc.score.toFixed(4)}</span>}
      {rel ? (
        <span className="fd__rel" title={rel === 2 ? "Judged highly relevant" : "Judged partly relevant"}>
          {rel === 2 ? "relevant" : "partial"}
        </span>
      ) : null}
    </li>
  );
}
