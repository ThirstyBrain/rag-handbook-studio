import { useEffect, useId, useMemo, useState } from "react";
import { chapterHrefByNumber, findExercise, getExerciseHelper } from "@/content/handbook";
import type { ExerciseRun } from "@/content/types";
import { track } from "@/shared/analytics/track";
import { highlight } from "@/shared/markdown/highlight";
import { Link } from "@/shared/router/router";
import { classifyOutput, sha256Hex } from "./outputLines";
import "./exercise-panel.css";

interface Props {
  file: string;
  /** Preselect the run with these arguments (e.g. "--mutants"). */
  args?: string;
  /** "tabs" in the reading column; "split" puts source and output side by side on wide screens. */
  layout?: "tabs" | "split";
  showChapterLink?: boolean;
}

type Tab = { id: string; label: string; kind: "output"; run: ExerciseRun } | { id: string; label: string; kind: "source"; file: string; code: string };


export function ExercisePanel({ file, args = "", layout = "tabs", showChapterLink }: Props) {
  const exercise = findExercise(file);
  const baseId = useId();

  const tabs = useMemo<Tab[]>(() => {
    if (!exercise) return [];
    const out: Tab[] = exercise.runs.map((run) => ({ id: `out:${run.args}`, label: run.args ? `Output ${run.args}` : "Output", kind: "output", run }));
    out.push({ id: "src", label: "Source", kind: "source", file: exercise.file, code: exercise.source });
    for (const h of exercise.helpers) {
      const code = getExerciseHelper(h);
      if (code) out.push({ id: `helper:${h}`, label: h, kind: "source", file: h, code });
    }
    return out;
  }, [exercise]);

  const initial = tabs.find((t) => t.kind === "output" && t.run.args === args)?.id ?? tabs[0]?.id ?? "src";
  const [active, setActive] = useState(initial);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    const run = exercise?.runs[0];
    if (!exercise || !run) return;
    let alive = true;
    void sha256Hex(exercise.source).then((h) => alive && h !== null && setStale(h !== run.sha256));
    return () => {
      alive = false;
    };
  }, [exercise]);

  if (!exercise) return null;

  const select = (id: string) => {
    setActive(id);
    track({ name: "exercise_tab", file, tab: id });
  };

  const outputTabs = tabs.filter((t) => t.kind === "output");
  const sourceTabs = tabs.filter((t) => t.kind === "source");
  const current = tabs.find((t) => t.id === active) ?? tabs[0]!;

  const onKeyDown = (e: React.KeyboardEvent, list: Tab[]) => {
    const i = list.findIndex((t) => t.id === active);
    if (i < 0) return;
    const next = e.key === "ArrowRight" ? list[(i + 1) % list.length] : e.key === "ArrowLeft" ? list[(i - 1 + list.length) % list.length] : null;
    if (next) {
      e.preventDefault();
      select(next.id);
      document.getElementById(`${baseId}-${next.id}`)?.focus();
    }
  };

  const head = (
    <header className="xp__head">
      <div className="xp__id">
        <span className="xp__file">{exercise.file}</span>
        {showChapterLink && exercise.chapter !== null && chapterHrefByNumber(exercise.chapter) && (
          <Link className="xp__chapter" href={chapterHrefByNumber(exercise.chapter)!}>
            Chapter {exercise.chapter}
          </Link>
        )}
      </div>
      <p className="xp__title">{exercise.title}</p>
    </header>
  );

  if (layout === "split") {
    const outTab = (current.kind === "output" ? current : outputTabs[0]) as Extract<Tab, { kind: "output" }> | undefined;
    const srcTab = (current.kind === "source" ? current : sourceTabs[0]) as Extract<Tab, { kind: "source" }>;
    return (
      <section className="xp xp--split" aria-label={`Exercise ${exercise.file}`}>
        {head}
        <div className="xp__split">
          <div className="xp__pane">
            <TabList tabs={sourceTabs} active={srcTab.id} onSelect={select} baseId={baseId} onKeyDown={(e) => onKeyDown(e, sourceTabs)} label="Source files" />
            <SourceView id={`${baseId}-panel-src`} code={srcTab.code} labelledBy={`${baseId}-${srcTab.id}`} />
          </div>
          <div className="xp__pane xp__pane--out">
            <TabList tabs={outputTabs} active={outTab?.id ?? ""} onSelect={select} baseId={baseId} onKeyDown={(e) => onKeyDown(e, outputTabs)} label="Captured runs" />
            {outTab ? <OutputView run={outTab.run} labelledBy={`${baseId}-${outTab.id}`} stale={stale} /> : <NoRun />}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="xp" aria-label={`Exercise ${exercise.file}`}>
      {head}
      <TabList tabs={tabs} active={current.id} onSelect={select} baseId={baseId} onKeyDown={(e) => onKeyDown(e, tabs)} label="Exercise views" />
      {current.kind === "output" ? (
        <OutputView run={current.run} labelledBy={`${baseId}-${current.id}`} stale={stale} />
      ) : (
        <SourceView id={`${baseId}-panel`} code={current.code} labelledBy={`${baseId}-${current.id}`} />
      )}
      {outputTabs.length === 0 && current.kind !== "source" && <NoRun />}
    </section>
  );
}

function TabList({ tabs, active, onSelect, baseId, onKeyDown, label }: { tabs: Tab[]; active: string; onSelect: (id: string) => void; baseId: string; onKeyDown: (e: React.KeyboardEvent) => void; label: string }) {
  return (
    <div className="xp__tabs" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
      {tabs.map((t) => (
        <button
          key={t.id}
          id={`${baseId}-${t.id}`}
          type="button"
          role="tab"
          data-focus-target={t.id === active ? "" : undefined}
          aria-selected={t.id === active}
          tabIndex={t.id === active ? 0 : -1}
          className="xp__tab"
          data-kind={t.kind}
          onClick={() => onSelect(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

function OutputView({ run, labelledBy, stale }: { run: ExerciseRun; labelledBy: string; stale: boolean }) {
  // The full captured output is always shown: nothing from the run is hidden or truncated.
  const lines = useMemo(() => classifyOutput([run.stdout, run.stderr].filter(Boolean).join("\n")), [run]);
  const ok = run.exitCode === 0;
  const when = new Date(run.capturedAt);

  return (
    <div className="xp__out" role="tabpanel" aria-labelledby={labelledBy}>
      <div className="xp__term" tabIndex={0} aria-label="Captured terminal output">
        <div className="xp__cmd">
          <span className="xp__prompt" aria-hidden="true">$</span> python -I docs/exercises/{run.file}
          {run.args && ` ${run.args}`}
        </div>
        <ol className="xp__lines">
          {lines.map((l, i) => (
            <li key={i} className={`xp__line xp__line--${l.kind}`}>
              {l.text || " "}
            </li>
          ))}
        </ol>
      </div>
      <footer className="xp__meta">
        <span className={`xp__exit ${ok ? "is-ok" : "is-fail"}`}>{ok ? "Exit 0" : `Exit ${run.exitCode}`}</span>
        <span>{run.durationMs} ms</span>
        <span>{run.python}</span>
        <span>
          Captured <time dateTime={run.capturedAt}>{when.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}</time>
        </span>
        {stale && <span className="xp__stale">The script changed after this capture. Run npm run exercises to refresh it.</span>}
      </footer>
    </div>
  );
}

function SourceView({ id, code, labelledBy }: { id: string; code: string; labelledBy: string }) {
  const { html } = useMemo(() => highlight(code, "python"), [code]);
  const lineCount = code.replace(/\n$/, "").split("\n").length;
  const [copied, setCopied] = useState(false);
  const copy = () =>
    void navigator.clipboard?.writeText(code).then(() => {
      setCopied(true);
      track({ name: "code_copied", language: "python" });
      window.setTimeout(() => setCopied(false), 1600);
    });
  return (
    <div className="xp__src" id={id} role="tabpanel" aria-labelledby={labelledBy}>
      <button type="button" className="code__copy xp__copy" onClick={copy} data-copied={copied || undefined}>
        {copied ? "Copied" : "Copy"}
      </button>
      <div className="xp__code" tabIndex={0} aria-label="Python source">
        <div className="xp__gutter" aria-hidden="true">
          {Array.from({ length: lineCount }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </div>
        <pre>
          <code className="hljs language-python" dangerouslySetInnerHTML={{ __html: html }} />
        </pre>
      </div>
    </div>
  );
}

function NoRun() {
  return <p className="xp__norun">No captured run yet. Run npm run exercises with Python on the PATH to record this script's output.</p>;
}
