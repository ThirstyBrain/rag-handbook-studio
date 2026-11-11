import { useEffect, useState } from "react";
import type { Chapter } from "@/content/types";
import { ChapterSidebar } from "./ChapterSidebar";
import { OnThisPage } from "./OnThisPage";

/**
 * Below 1024px the rails disappear; this sticky bar names the current section and opens a
 * bottom sheet with the outline and the chapter list.
 */
export function ReaderBar({ chapter, activeTitle, activeId, progress }: { chapter: Chapter; activeTitle: string; activeId: string | null; progress: number }) {
  const [open, setOpen] = useState<"none" | "outline" | "chapters">("none");

  useEffect(() => {
    if (open === "none") return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen("none");
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  const close = () => setOpen("none");

  return (
    <>
      <div className="reader-bar">
        <button type="button" className="reader-bar__btn" onClick={() => setOpen("outline")} aria-haspopup="dialog" aria-expanded={open === "outline"}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            <path d="M2 4h12M2 8h8M2 12h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span className="reader-bar__label">
            <span className="reader-bar__ch">Ch. {chapter.number}</span>
            <span className="reader-bar__sec">{activeTitle}</span>
          </span>
          <span className="reader-bar__pct">{Math.round(progress * 100)}%</span>
        </button>
      </div>

      {open !== "none" && (
        <div className="sheet-layer" role="dialog" aria-modal="true" aria-label={open === "outline" ? "Chapter outline" : "Chapters"}>
          <button type="button" className="sheet-scrim" aria-label="Close" onClick={close} />
          <div className="sheet">
            <div className="sheet__head">
              <div className="sheet__tabs" role="tablist">
                <button type="button" role="tab" aria-selected={open === "outline"} onClick={() => setOpen("outline")}>
                  This chapter
                </button>
                <button type="button" role="tab" aria-selected={open === "chapters"} onClick={() => setOpen("chapters")}>
                  All chapters
                </button>
              </div>
              <button type="button" className="btn btn--quiet btn--small" onClick={close}>
                Close
              </button>
            </div>
            <div className="sheet__body">
              {open === "outline" ? (
                <OnThisPage chapter={chapter} activeId={activeId} progress={progress} onNavigate={close} compact />
              ) : (
                <ChapterSidebar current={chapter.number} onNavigate={close} />
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
