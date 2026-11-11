import { useEffect, useRef } from "react";

/** On route change: scroll to the hash target if there is one, otherwise to the top. */
export function useScrollRestoration(location: { path: string; hash: string }) {
  const lastPath = useRef<string | null>(null);
  useEffect(() => {
    const pathChanged = lastPath.current !== location.path;
    lastPath.current = location.path;
    if (location.hash) {
      // Wait a frame so lazily rendered content (chapter bodies) exists.
      let tries = 0;
      const tryScroll = () => {
        const el = document.getElementById(location.hash);
        if (el) el.scrollIntoView({ block: "start" });
        else if (tries++ < 20) requestAnimationFrame(tryScroll);
      };
      requestAnimationFrame(tryScroll);
    } else if (pathChanged) {
      window.scrollTo({ top: 0 });
    }
  }, [location.path, location.hash]);
}
