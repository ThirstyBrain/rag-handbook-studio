import { useEffect, useRef } from "react";
import { EVIDENCE_LABELS, EVIDENCE_SHORT } from "@/content/parse/evidence";
import type { Chapter, EvidenceKind } from "@/content/types";

const KINDS: EvidenceKind[] = ["X", "S", "E", "V", "I", "A", "N"];

interface Props {
  chapter: Chapter;
  activeId: string | null;
  progress: number;
  focus?: string | null;
  onFocus?: (k: string | null) => void;
  onNavigate?: () => void;
  compact?: boolean;
}

/** Section outline with scroll-spy, plus the evidence highlighter. */
export function OnThisPage({ chapter, activeId, progress, focus, onFocus, onNavigate, compact }: Props) {
  const listRef = useRef<HTMLOListElement>(null);
  const activeH2 = (() => {
    let last: string | null = null;
    for (const s of chapter.sections) {
      if (s.level === 2) last = s.id;
      if (s.id === activeId) break;
    }
    return last;
  })();

  useEffect(() => {
    if (compact) return;
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="location"]');
    const list = listRef.current;
    if (el && list) {
      const top = el.offsetTop - list.clientHeight / 2;
      list.scrollTo?.({ top, behavior: "auto" });
    }
  }, [activeId, compact]);

  const go = (id: string) => (e: React.MouseEvent) => {
    e.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    window.history.replaceState(null, "", `#${id}`);
    onNavigate?.();
  };

  // Show all H2s, and the H3s of the H2 currently being read.
  let parent: string | null = null;
  const visible = chapter.sections.filter((s) => {
    if (s.level === 2) {
      parent = s.id;
      return true;
    }
    return compact || parent === activeH2;
  });

  return (
    <div className={`otp${compact ? " otp--compact" : ""}`}>
      {!compact && (
        <div className="otp__progress">
          <span>On this page</span>
          <span className="otp__pct">{Math.round(progress * 100)}%</span>
        </div>
      )}
      <ol ref={listRef} className="otp__list">
        {visible.map((s) => (
          <li key={s.id} className={`otp__item otp__item--l${s.level}`}>
            <a href={`#${s.id}`} onClick={go(s.id)} aria-current={s.id === activeId ? "location" : undefined}>
              {s.number && <span className="otp__num">{s.number}</span>}
              <span>{s.title}</span>
            </a>
          </li>
        ))}
      </ol>

      {onFocus && (
        <div className="otp__evidence">
          <p className="otp__evidence-title" id="evidence-focus-label">
            Highlight claims by evidence
          </p>
          <div className="otp__evidence-list" role="group" aria-labelledby="evidence-focus-label">
            {KINDS.filter((k) => chapter.evidence[k]).map((k) => (
              <button
                key={k}
                type="button"
                className="otp__ev"
                aria-pressed={focus === k}
                title={EVIDENCE_LABELS[k]}
                onClick={() => onFocus(focus === k ? null : k)}
              >
                <span className={`evidence-bar__dot ev-bg--${k.toLowerCase()}`} aria-hidden="true" />
                {EVIDENCE_SHORT[k]}
                <span className="otp__ev-n">{chapter.evidence[k]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {!compact && (
        <p className="otp__keys">
          <kbd className="kbd">[</kbd> <kbd className="kbd">]</kbd> previous / next chapter
        </p>
      )}
    </div>
  );
}
