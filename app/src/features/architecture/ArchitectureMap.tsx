import { useRef } from "react";
import { getHandbook } from "@/content/handbook";
import { LANE_LABEL, STAGES, type Lane } from "./stages";

/** Node geometry for the SVG blueprint (viewBox units). */
const W = 152;
const H = 58;
const POS: Record<string, { x: number; y: number; w?: number }> = {
  ingest: { x: 40, y: 70 },
  chunk: { x: 218, y: 70 },
  embed: { x: 396, y: 70 },
  index: { x: 574, y: 70 },
  transform: { x: 40, y: 236 },
  filter: { x: 218, y: 236 },
  retrieve: { x: 396, y: 236 },
  rerank: { x: 574, y: 236 },
  assemble: { x: 752, y: 236 },
  generate: { x: 930, y: 236 },
  agent: { x: 485, y: 346 },
  isolation: { x: 40, y: 452, w: 508 },
  evaluate: { x: 574, y: 452, w: 508 },
};

type Edge = { from: string; to: string; kind?: "store" | "loop" };
const EDGES: Edge[] = [
  { from: "ingest", to: "chunk" },
  { from: "chunk", to: "embed" },
  { from: "embed", to: "index" },
  { from: "index", to: "retrieve", kind: "store" },
  { from: "transform", to: "filter" },
  { from: "filter", to: "retrieve" },
  { from: "retrieve", to: "rerank" },
  { from: "rerank", to: "assemble" },
  { from: "assemble", to: "generate" },
  { from: "generate", to: "agent", kind: "loop" },
  { from: "agent", to: "transform", kind: "loop" },
];

function edgePath(e: Edge): string {
  const a = POS[e.from]!;
  const b = POS[e.to]!;
  if (e.kind === "store") {
    const x1 = a.x + W / 2;
    const y1 = a.y + H;
    const x2 = b.x + W / 2;
    const y2 = b.y;
    return `M${x1} ${y1} C ${x1} ${y1 + 60}, ${x2 + 60} ${y2 - 60}, ${x2} ${y2}`;
  }
  if (e.kind === "loop" && e.from === "generate") {
    const x1 = a.x + W / 2;
    const y1 = a.y + H;
    const x2 = b.x + W;
    const y2 = b.y + H / 2;
    return `M${x1} ${y1} C ${x1} ${y2}, ${x2 + 120} ${y2}, ${x2} ${y2}`;
  }
  if (e.kind === "loop") {
    const x1 = a.x;
    const y1 = a.y + H / 2;
    const x2 = b.x + W / 2;
    const y2 = b.y + H;
    return `M${x1} ${y1} C ${x1 - 160} ${y1}, ${x2} ${y1}, ${x2} ${y2}`;
  }
  return `M${a.x + W} ${a.y + H / 2} L ${b.x} ${b.y + H / 2}`;
}

interface Props {
  selected: string;
  onSelect: (id: string) => void;
  compact: boolean;
}

export function ArchitectureMap({ selected, onSelect, compact }: Props) {
  const hb = getHandbook();
  const written = new Set(hb.chapters.map((c) => c.number));
  const refs = useRef<Record<string, SVGGElement | HTMLButtonElement | null>>({});

  const move = (id: string, dir: 1 | -1) => {
    const i = STAGES.findIndex((s) => s.id === id);
    const next = STAGES[(i + dir + STAGES.length) % STAGES.length]!;
    onSelect(next.id);
    refs.current[next.id]?.focus();
  };

  const onKey = (id: string) => (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(id);
    } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      move(id, 1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      move(id, -1);
    }
  };

  const isPlanned = (id: string) => !STAGES.find((s) => s.id === id)!.chapters.some((n) => written.has(n));
  const active = (e: Edge) => e.from === selected || e.to === selected;

  if (compact) {
    const lanes: Lane[] = ["offline", "online", "cross"];
    return (
      <div className="amap-list">
        {lanes.map((lane) => (
          <div key={lane} className="amap-list__lane">
            <p className="amap-list__label">{LANE_LABEL[lane]}</p>
            <ol>
              {STAGES.filter((s) => s.lane === lane).map((s) => (
                <li key={s.id}>
                  <button
                    ref={(el) => (refs.current[s.id] = el)}
                    type="button"
                    className={`amap-list__btn amap-list__btn--${lane}`}
                    aria-pressed={s.id === selected}
                    data-planned={isPlanned(s.id) || undefined}
                    onClick={() => onSelect(s.id)}
                  >
                    <span>{s.name}</span>
                    <span className="amap-list__ch">{isPlanned(s.id) ? "Planned" : s.chapters.filter((n) => written.has(n)).map((n) => `Ch. ${n}`).join(", ")}</span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="amap" role="group" aria-label="Architecture map. Use arrow keys to move between stages.">
      <svg viewBox="0 0 1122 540" className="amap__svg">
        <defs>
          <pattern id="amap-grid" width="16" height="16" patternUnits="userSpaceOnUse">
            <path d="M16 0H0V16" fill="none" stroke="rgb(159 179 200 / 0.08)" strokeWidth="1" />
          </pattern>
          <linearGradient id="amap-selected" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#31d4e5" />
            <stop offset="1" stopColor="#00a6a6" />
          </linearGradient>
          <marker id="amap-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0L10 5L0 10z" fill="currentColor" />
          </marker>
        </defs>
        <rect x="0" y="0" width="1122" height="540" fill="url(#amap-grid)" />

        <text x="40" y="52" className="amap__lane">
          {LANE_LABEL.offline}
        </text>
        <text x="40" y="218" className="amap__lane">
          {LANE_LABEL.online}
        </text>
        <text x="40" y="434" className="amap__lane">
          {LANE_LABEL.cross}
        </text>
        <line x1="40" x2="1082" y1="176" y2="176" className="amap__divider" />
        <line x1="40" x2="1082" y1="412" y2="412" className="amap__divider" />

        {EDGES.map((e) => (
          <path key={`${e.from}-${e.to}`} d={edgePath(e)} className={`amap__edge${e.kind ? ` amap__edge--${e.kind}` : ""}`} data-active={active(e) || undefined} markerEnd="url(#amap-arrow)" />
        ))}
        <text x="660" y="420" className="amap__note">
          Loops back when the evidence is insufficient
        </text>

        {STAGES.map((s, i) => {
          const p = POS[s.id]!;
          const w = p.w ?? W;
          const planned = isPlanned(s.id);
          return (
            <g
              key={s.id}
              ref={(el) => (refs.current[s.id] = el)}
              className={`amap__node amap__node--${s.lane}`}
              data-selected={s.id === selected || undefined}
              data-planned={planned || undefined}
              role="button"
              tabIndex={s.id === selected ? 0 : -1}
              aria-pressed={s.id === selected}
              aria-label={`${s.name}${planned ? ", planned" : ""}`}
              onClick={() => onSelect(s.id)}
              onKeyDown={onKey(s.id)}
            >
              <rect x={p.x} y={p.y} width={w} height={H} rx="6" />
              <text x={p.x + 14} y={p.y + 24} className="amap__name">
                {s.name}
              </text>
              <text x={p.x + 14} y={p.y + 43} className="amap__meta">
                {planned ? "Planned, chapters not written" : `${i + 1}. Chapter${s.chapters.filter((n) => written.has(n)).length > 1 ? "s" : ""} ${s.chapters.filter((n) => written.has(n)).join(", ")}`}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
