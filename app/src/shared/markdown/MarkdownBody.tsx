import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { track } from "../analytics/track";
import { useRouter } from "../router/router";
import { Dialog } from "../ui/Dialog";
import { renderMermaid } from "./mermaid";
import "./markdown-body.css";

export interface SourceAnchor {
  id: string;
  rect: DOMRect;
}

interface Props {
  html: string;
  className?: string;
  /** Render an exercise panel into a slot produced by renderMarkdown. */
  renderExercise?: (file: string, args: string) => ReactNode;
  /** Called when an evidence source chip ([S67]) is activated. */
  onSource?: (anchor: SourceAnchor) => void;
  evidenceFocus?: string | null;
}

/** Static HTML is injected once; a memoised inner component keeps React from re-writing it. */
const StaticHtml = memo(function StaticHtml({ html, className, focus, innerRef }: { html: string; className?: string; focus?: string | null; innerRef: React.Ref<HTMLDivElement> }) {
  return <div ref={innerRef} className={className} data-evidence-focus={focus ?? undefined} dangerouslySetInnerHTML={{ __html: html }} />;
});

export function MarkdownBody({ html, className = "prose", renderExercise, onSource, evidenceFocus }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const { navigate } = useRouter();
  const [slots, setSlots] = useState<HTMLElement[]>([]);
  const [expanded, setExpanded] = useState<{ svg: string; title: string } | null>(null);

  useLayoutEffect(() => {
    setSlots(ref.current ? [...ref.current.querySelectorAll<HTMLElement>(".exercise-slot")] : []);
  }, [html]);

  // Every diagram renders as soon as the page mounts, in document order (Mermaid renders serially).
  // Rendering is not tied to scrolling, so diagrams are present for fast scrolling, find-in-page,
  // printing and background tabs. Until a diagram is drawn its Mermaid source is shown.
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const figures = [...root.querySelectorAll<HTMLElement>("figure.diagram[data-mermaid]")];
    const draw = async (fig: HTMLElement) => {
      if (fig.dataset.state) return;
      fig.dataset.state = "loading";
      try {
        const svg = await renderMermaid(decodeURIComponent(fig.dataset.mermaid ?? ""));
        // The figure node outlives effect re-runs (the HTML is memoised), so write whenever it is still on the page.
        if (!fig.isConnected) return;
        fig.innerHTML = svg;
        fig.dataset.state = "ready";
        fig.setAttribute("role", "img");
        const caption = fig.nextElementSibling?.textContent?.trim() ?? "Architecture diagram";
        fig.setAttribute("aria-label", caption);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "diagram__expand";
        btn.textContent = "Expand";
        btn.dataset.expand = "";
        fig.appendChild(btn);
      } catch {
        if (fig.isConnected) fig.dataset.state = "error";
      }
    };
    figures.forEach((f) => void draw(f));
  }, [html]);

  const onClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = e.target as HTMLElement;
      const copy = target.closest<HTMLButtonElement>("[data-copy]");
      if (copy) {
        const code = copy.closest(".code")?.querySelector("pre")?.textContent ?? "";
        void navigator.clipboard?.writeText(code).then(() => {
          copy.textContent = "Copied";
          copy.dataset.copied = "";
          track({ name: "code_copied", language: copy.closest<HTMLElement>(".code")?.dataset.lang ?? "" });
          window.setTimeout(() => {
            copy.textContent = "Copy";
            delete copy.dataset.copied;
          }, 1600);
        });
        return;
      }
      const expand = target.closest<HTMLElement>("[data-expand]");
      if (expand) {
        const fig = expand.closest("figure");
        const svg = fig?.querySelector("svg")?.outerHTML;
        if (svg) {
          const title = fig?.getAttribute("aria-label") ?? "Diagram";
          setExpanded({ svg, title });
          track({ name: "diagram_expanded", file: title.slice(0, 80) });
        }
        return;
      }
      const source = target.closest<HTMLAnchorElement>("a[data-source]");
      if (source && onSource) {
        e.preventDefault();
        onSource({ id: source.dataset.source!, rect: source.getBoundingClientRect() });
        return;
      }
      const a = target.closest<HTMLAnchorElement>("a[href]");
      if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const href = a.getAttribute("href")!;
      if (href.startsWith("#")) {
        e.preventDefault();
        const el = document.getElementById(decodeURIComponent(href.slice(1)));
        el?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
        window.history.replaceState(null, "", href);
        if (el?.classList.contains("exercise-slot")) el.querySelector<HTMLElement>("[data-focus-target]")?.focus({ preventScroll: true });
      } else if (href.startsWith("/")) {
        e.preventDefault();
        navigate(href);
      }
    },
    [navigate, onSource],
  );

  return (
    <div onClick={onClick}>
      <StaticHtml html={html} className={className} focus={evidenceFocus} innerRef={ref} />
      {renderExercise && slots.map((el, i) => createPortal(renderExercise(el.dataset.exercise ?? "", el.dataset.args ?? ""), el, `slot-${i}`))}
      <Dialog open={!!expanded} onClose={() => setExpanded(null)} title={expanded?.title ?? ""} wide>
        {expanded && <div className="diagram-zoom" dangerouslySetInnerHTML={{ __html: expanded.svg }} />}
      </Dialog>
    </div>
  );
}
