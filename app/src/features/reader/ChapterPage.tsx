import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { findChapter, getHandbook } from "@/content/handbook";
import { handbookRenderContext } from "@/content/renderContext";
import type { Chapter } from "@/content/types";
import { track } from "@/shared/analytics/track";
import { MarkdownBody, type SourceAnchor } from "@/shared/markdown/MarkdownBody";
import { renderMarkdown } from "@/shared/markdown/render";
import { useRouter } from "@/shared/router/router";
import { ExercisePanel } from "@/features/exercises/ExercisePanel";
import { NotFound } from "@/app/NotFound";
import { ChapterHeader } from "./ChapterHeader";
import { ChapterFooter } from "./ChapterFooter";
import { ChapterSidebar } from "./ChapterSidebar";
import { OnThisPage } from "./OnThisPage";
import { ReaderBar } from "./ReaderBar";
import { markCompleted, setLastRead } from "./readingState";
import { SourcePopover } from "./SourcePopover";
import { useScrollSpy } from "./useScrollSpy";
import "./reader.css";

export default function ChapterPage({ params }: { params: Record<string, string> }) {
  const chapter = findChapter(params.slug ?? "");
  if (!chapter) return <NotFound />;
  return <Reader key={chapter.slug} chapter={chapter} />;
}

function Reader({ chapter }: { chapter: Chapter }) {
  const hb = getHandbook();
  const { navigate } = useRouter();
  const articleRef = useRef<HTMLElement>(null);
  const [source, setSource] = useState<SourceAnchor | null>(null);
  const [focus, setFocus] = useState<string | null>(null);

  const rendered = useMemo(() => renderMarkdown(chapter.markdown, handbookRenderContext()), [chapter]);
  const tocIds = useMemo(() => chapter.sections.map((s) => s.id), [chapter]);
  const { active, progress } = useScrollSpy(tocIds, articleRef);

  const index = hb.chapters.findIndex((c) => c.number === chapter.number);
  const prev = hb.chapters[index - 1];
  const next = hb.chapters[index + 1];

  useEffect(() => {
    if (progress >= 0.98 && markCompleted(chapter.number)) track({ name: "chapter_completed", chapter: chapter.number });
  }, [progress, chapter.number]);

  // Remember the place, so "Continue reading" in the header returns here.
  useEffect(() => {
    setLastRead({ slug: chapter.slug, sectionId: active });
  }, [chapter.slug, active]);

  // "[" and "]" move between chapters, as in many documentation readers.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable) return;
      if (e.key === "]" && next) navigate(`/handbook/${next.slug}`);
      if (e.key === "[" && prev) navigate(`/handbook/${prev.slug}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navigate, next, prev]);

  // In the reader, code and its captured output are shown together (stacked in the reading column).
  const renderExercise = useCallback((file: string, args: string) => <ExercisePanel file={file} args={args} layout="split" showChapterLink={false} />, []);
  const closeSource = useCallback(() => setSource(null), []);
  const activeSection = chapter.sections.find((s) => s.id === active);

  return (
    <div className="reader-wrap">
      <div className="reading-progress" aria-hidden="true">
        <span style={{ transform: `scaleX(${progress})` }} />
      </div>
      <ReaderBar chapter={chapter} activeTitle={activeSection ? `${activeSection.number} ${activeSection.title}`.trim() : chapter.title} activeId={active} progress={progress} />

      <div className="reader page">
        <ChapterSidebar current={chapter.number} />

        <article ref={articleRef} className="reader__article" aria-labelledby="chapter-title">
          <ChapterHeader chapter={chapter} />
          <MarkdownBody html={rendered.html} renderExercise={renderExercise} onSource={setSource} evidenceFocus={focus} />
          <ChapterFooter chapter={chapter} prev={prev} next={next} />
        </article>

        <aside className="reader__rail" aria-label="On this page">
          <OnThisPage chapter={chapter} activeId={active} progress={progress} focus={focus} onFocus={setFocus} />
        </aside>
      </div>

      {source && <SourcePopover anchor={source} onClose={closeSource} />}
    </div>
  );
}
