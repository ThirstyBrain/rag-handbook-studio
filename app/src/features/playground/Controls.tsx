import { useId } from "react";
import type { HybridSettings } from "./domain/hybrid";

interface SliderProps {
  label: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  step: number;
  format?: (v: number) => string;
  onChange: (v: number) => void;
}

function Slider({ label, hint, value, min, max, step, format = (v) => String(v), onChange }: SliderProps) {
  const id = useId();
  return (
    <div className="ctl">
      <div className="ctl__row">
        <label htmlFor={id} className="ctl__label">
          {label}
        </label>
        <output htmlFor={id} className="ctl__value">
          {format(value)}
        </output>
      </div>
      <input id={id} type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="ctl__range" aria-describedby={`${id}-hint`} />
      <p id={`${id}-hint`} className="ctl__hint">
        {hint}
      </p>
    </div>
  );
}

export function Controls({ settings, onChange, onReset, changed }: { settings: HybridSettings; onChange: (s: HybridSettings) => void; onReset: () => void; changed: boolean }) {
  const set = (patch: Partial<HybridSettings>) => onChange({ ...settings, ...patch });
  return (
    <div className="controls">
      <div className="controls__head">
        <h2 className="lab__side-h">Parameters</h2>
        <button type="button" className="btn btn--quiet btn--small" onClick={onReset} disabled={!changed}>
          Reset to script
        </button>
      </div>
      <Slider label="RRF constant k" hint="60 in the script and the original paper. Low k lets one leg's top hit dominate; high k rewards agreement." value={settings.k} min={0} max={200} step={1} onChange={(k) => set({ k })} />
      <Slider
        label="Keyword leg weight"
        hint="Weighted RRF and weighted min–max. 1.0 in the script."
        value={settings.weights[0]}
        min={0}
        max={3}
        step={0.1}
        format={(v) => v.toFixed(1)}
        onChange={(w) => set({ weights: [w, settings.weights[1]] })}
      />
      <Slider
        label="Semantic leg weight"
        hint="1.0 in the script."
        value={settings.weights[1]}
        min={0}
        max={3}
        step={0.1}
        format={(v) => v.toFixed(1)}
        onChange={(w) => set({ weights: [settings.weights[0], w] })}
      />
      <Slider label="Candidates per leg" hint="How many results each leg passes to fusion. 8, the whole corpus, in the script." value={settings.candidateK} min={1} max={8} step={1} onChange={(candidateK) => set({ candidateK })} />
      <Slider label="BM25 k1" hint="Term-frequency saturation. 1.2 by default; 0 means only IDF counts." value={settings.bm25.k1} min={0} max={3} step={0.1} format={(v) => v.toFixed(1)} onChange={(k1) => set({ bm25: { ...settings.bm25, k1 } })} />
      <Slider label="BM25 b" hint="Length normalisation. 0.75 by default; 0 ignores document length." value={settings.bm25.b} min={0} max={1} step={0.05} format={(v) => v.toFixed(2)} onChange={(b) => set({ bm25: { ...settings.bm25, b } })} />
    </div>
  );
}
