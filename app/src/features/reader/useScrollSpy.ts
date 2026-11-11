import { useEffect, useState } from "react";

/**
 * Tracks which heading the reader is in and how far through the article they are.
 * One passive scroll listener, coalesced to one measurement per frame.
 */
export function useScrollSpy(ids: string[], articleRef: React.RefObject<HTMLElement>, offset = 140) {
  const [active, setActive] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let frame = 0;
    const measure = () => {
      frame = 0;
      let current: string | null = null;
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        if (el.getBoundingClientRect().top - offset <= 0) current = id;
        else break;
      }
      setActive(current);
      const article = articleRef.current;
      if (article) {
        const rect = article.getBoundingClientRect();
        const total = rect.height - window.innerHeight * 0.6;
        setProgress(total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : 1);
      }
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [ids, articleRef, offset]);

  return { active, progress };
}
