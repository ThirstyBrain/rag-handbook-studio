import { createContext, lazy, Suspense, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { track } from "@/shared/analytics/track";

const SearchPalette = lazy(() => import("./SearchPalette"));

interface SearchValue {
  open: (source: "shortcut" | "button", query?: string) => void;
}

const SearchContext = createContext<SearchValue>({ open: () => {} });

export function SearchProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ open: boolean; query: string }>({ open: false, query: "" });

  const open = useCallback((source: "shortcut" | "button", query = "") => {
    setState({ open: true, query });
    track({ name: "search_opened", source });
  }, []);

  // Warm the palette chunk when the browser is idle, so the first Ctrl K opens instantly and no keystroke is lost.
  useEffect(() => {
    const preload = () => void import("./SearchPalette");
    const w = window as Window & { requestIdleCallback?: (cb: () => void) => number };
    if (w.requestIdleCallback) w.requestIdleCallback(preload);
    else window.setTimeout(preload, 1500);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        open("shortcut");
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        open("shortcut");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const value = useMemo(() => ({ open }), [open]);
  return (
    <SearchContext.Provider value={value}>
      {children}
      {state.open && (
        <Suspense fallback={null}>
          <SearchPalette initialQuery={state.query} onClose={() => setState({ open: false, query: "" })} />
        </Suspense>
      )}
    </SearchContext.Provider>
  );
}

export const useSearch = () => useContext(SearchContext);
