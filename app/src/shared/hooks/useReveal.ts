import { useEffect, useRef } from "react";

/**
 * Progressive reveal: content is visible by default. Only an element that starts below the fold,
 * in a browser with IntersectionObserver and without reduced motion, is briefly hidden and then
 * revealed once as it scrolls in. Nothing is ever left hidden if the observer does not fire.
 */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const belowFold = el.getBoundingClientRect().top > window.innerHeight;
    if (!("IntersectionObserver" in window) || reduce || !belowFold || document.visibilityState !== "visible") return;
    el.dataset.revealPending = "";
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          delete el.dataset.revealPending;
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    io.observe(el);
    // Safety net: never leave content hidden.
    const timer = window.setTimeout(() => delete el.dataset.revealPending, 4000);
    return () => {
      io.disconnect();
      window.clearTimeout(timer);
      delete el.dataset.revealPending;
    };
  }, []);
  return ref;
}
