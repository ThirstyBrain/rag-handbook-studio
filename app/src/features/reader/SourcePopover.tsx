import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getHandbook } from "@/content/handbook";
import type { SourceAnchor } from "@/shared/markdown/MarkdownBody";
import { Link } from "@/shared/router/router";

/** Shows the citation behind an [S#] mark next to the mark itself. */
export function SourcePopover({ anchor, onClose }: { anchor: SourceAnchor; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ top: number; left: number }>({ top: -9999, left: 0 });
  const ref_ = getHandbook().references.get(anchor.id);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth;
    const h = el.offsetHeight;
    const margin = 12;
    let left = anchor.rect.left + anchor.rect.width / 2 - w / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - w - margin));
    let top = anchor.rect.bottom + 8;
    if (top + h > window.innerHeight - margin) top = anchor.rect.top - h - 8;
    setPos({ top, left });
    el.focus();
  }, [anchor]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onDown = (e: PointerEvent) => !ref.current?.contains(e.target as Node) && onClose();
    const onScroll = () => onClose();
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", onScroll, { passive: true, once: true });
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", onScroll);
    };
  }, [onClose]);

  return (
    <div ref={ref} className="source-pop" role="dialog" aria-label={`Source ${anchor.id}`} tabIndex={-1} style={{ top: pos.top, left: pos.left }}>
      <p className="source-pop__id">{anchor.id}</p>
      {ref_ ? (
        <>
          <p className="source-pop__cite">{ref_.citation.replace(/\s*https?:\/\/\S+/g, "")}</p>
          {ref_.status && <p className="source-pop__status">Reviewed: {ref_.status}</p>}
          <div className="source-pop__actions">
            {ref_.url && (
              <a className="btn btn--quiet btn--small" href={ref_.url} target="_blank" rel="noopener noreferrer">
                Open source
              </a>
            )}
            <Link className="btn btn--quiet btn--small" href={`/references#${anchor.id}`} onClick={onClose}>
              All references
            </Link>
          </div>
        </>
      ) : (
        <p className="source-pop__cite">This source id is not in the handbook's reference list yet.</p>
      )}
    </div>
  );
}
