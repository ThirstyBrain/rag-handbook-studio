import { useMemo } from "react";
import { chapterHref, getHandbook } from "@/content/handbook";
import { handbookRenderContext } from "@/content/renderContext";
import type { Chapter } from "@/content/types";
import { track } from "@/shared/analytics/track";
import { renderMarkdown } from "@/shared/markdown/render";
import { Link } from "@/shared/router/router";
import { Icon } from "@/shared/ui/Icon";
import { ExercisePanel } from "./ExercisePanel";
import { questionKey, useCheckpointProgress } from "./checkpointState";
import "./exercises-page.css";

/**
 * Practice, chapter by chapter: the handbook's own knowledge-checkpoint questions, plus the
 * scripts behind the chapter's executed claims, each with its full source and real captured run.
 */
export default function ExercisesPage() {
  const hb = getHandbook();
  const { done, toggle } = useCheckpointProgress();
  const chapters = hb.chapters.filter((c) => c.checkpoint.length > 0 || hb.exercises.some((e) => e.chapter === c.number));
  const totalQ = chapters.reduce((s, c) => s + c.checkpoint.length, 0);
  const doneQ = chapters.reduce((s, c) => s + c.checkpoint.filter((q) => done[questionKey(c.number, q)]).length, 0);
  const runs = hb.exercises.flatMap((e) => e.runs);
  const ok = runs.filter((r) => r.exitCode === 0).length;

  return (
    <div className="page exs">
      <header className="page-head">
        <p className="page-head__eyebrow">Practise</p>
        <h1 className="page-head__title">Exercises</h1>
        <p className="page-head__lede">
          Each chapter's knowledge-checkpoint questions, next to the scripts behind its executed claims with their real output. Mark questions done as you work; progress stays on this device.
        </p>
      </header>

      <section className="exs__overview" aria-label="Your progress">
        <div className="exs__stat">
          <span className="exs__stat-n">
            {doneQ}
            <small> / {totalQ}</small>
          </span>
          <span className="exs__stat-l">Checkpoint questions done</span>
          <span className="exs__meter" role="progressbar" aria-valuemin={0} aria-valuemax={totalQ} aria-valuenow={doneQ} aria-label="Questions done">
            <span style={{ width: `${totalQ ? (doneQ / totalQ) * 100 : 0}%` }} />
          </span>
        </div>
        <div className="exs__stat">
          <span className="exs__stat-n">{hb.exercises.length}</span>
          <span className="exs__stat-l">Runnable scripts, standard-library Python</span>
        </div>
        <div className="exs__stat">
          <span className="exs__stat-n">
            {ok}
            <small> / {runs.length}</small>
          </span>
          <span className="exs__stat-l">Captured runs that exited cleanly</span>
        </div>
      </section>

      <div className="exs__layout">
        <nav className="exs__index" aria-label="Chapters with exercises">
          <ol>
            {chapters.map((c) => {
              const d = c.checkpoint.filter((q) => done[questionKey(c.number, q)]).length;
              return (
                <li key={c.number}>
                  <a href={`#practice-${c.number}`} className="exs__link">
                    <span className="exs__ch">{c.number}</span>
                    <span className="exs__name">{c.title}</span>
                    {c.checkpoint.length > 0 && (
                      <span className="exs__mini" data-complete={d === c.checkpoint.length || undefined}>
                        {d}/{c.checkpoint.length}
                      </span>
                    )}
                  </a>
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="exs__list">
          {chapters.map((c) => (
            <ChapterPractice key={c.number} chapter={c} done={done} onToggle={toggle} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ChapterPractice({ chapter, done, onToggle }: { chapter: Chapter; done: Record<string, true>; onToggle: (key: string) => void }) {
  const hb = getHandbook();
  const scripts = hb.exercises.filter((e) => e.chapter === chapter.number);
  const ctx = handbookRenderContext();
  const questions = useMemo(() => chapter.checkpoint.map((q) => ({ text: q, html: renderMarkdown(q, { ...ctx, exercises: undefined }).html })), [chapter, ctx]);
  const d = chapter.checkpoint.filter((q) => done[questionKey(chapter.number, q)]).length;

  return (
    <section id={`practice-${chapter.number}`} className="exs__item" aria-labelledby={`h-practice-${chapter.number}`}>
      <header className="exs__item-head">
        <p className="exs__item-num">Chapter {chapter.number}</p>
        <h2 id={`h-practice-${chapter.number}`} className="exs__title">
          <Link href={chapterHref(chapter)}>{chapter.title}</Link>
        </h2>
        {questions.length > 0 && (
          <p className="exs__item-progress">
            {d} of {questions.length} done
          </p>
        )}
      </header>

      {questions.length > 0 && (
        <ol className="exs__questions">
          {questions.map((q, i) => {
            const key = questionKey(chapter.number, q.text);
            const isDone = !!done[key];
            return (
              <li key={key} className="exs__q" data-done={isDone || undefined}>
                <span className="exs__q-n" aria-hidden="true">
                  {i + 1}
                </span>
                <div className="exs__q-body prose" dangerouslySetInnerHTML={{ __html: q.html }} />
                <button
                  type="button"
                  className="exs__q-toggle"
                  aria-pressed={isDone}
                  aria-label={`${isDone ? "Mark not done" : "Mark done"}: question ${i + 1}`}
                  onClick={() => {
                    onToggle(key);
                    track({ name: "exercise_tab", file: `checkpoint-${chapter.number}`, tab: isDone ? "undone" : "done" });
                  }}
                >
                  <Icon name="check" size={18} />
                  <span>{isDone ? "Done" : "Mark done"}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
      {chapter.checkpointSectionId && (
        <p className="exs__source">
          From <Link href={chapterHref(chapter, chapter.checkpointSectionId)}>the chapter's checkpoint section</Link>. The handbook does not publish answer keys; each question points back to the sections and scripts that settle it.
        </p>
      )}

      {scripts.map((x) => (
        <div key={x.file} id={x.file.replace(/\.py$/, "")} className="exs__script">
          <ExercisePanel file={x.file} layout="split" />
        </div>
      ))}
    </section>
  );
}
