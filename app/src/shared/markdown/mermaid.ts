import { createLogger } from "../logging/log";

const log = createLogger("mermaid");
type MermaidApi = typeof import("mermaid").default;

let api: Promise<MermaidApi> | null = null;
let queue: Promise<unknown> = Promise.resolve();
let counter = 0;

/** Mermaid is ~1MB, so it loads on first use and renders serially (its renderer is not re-entrant). */
function load(): Promise<MermaidApi> {
  api ??= import("mermaid").then(({ default: m }) => {
    const css = getComputedStyle(document.documentElement);
    const v = (name: string) => css.getPropertyValue(name).trim();
    m.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: v("--font-sans"),
      flowchart: { curve: "basis", htmlLabels: true, padding: 12, nodeSpacing: 36, rankSpacing: 44 },
      sequence: { mirrorActors: false },
      themeVariables: {
        fontSize: "14px",
        background: "transparent",
        primaryColor: "#ffffff",
        primaryBorderColor: v("--navy"),
        primaryTextColor: v("--ink"),
        secondaryColor: v("--teal-wash"),
        secondaryBorderColor: v("--teal"),
        tertiaryColor: v("--blue-wash"),
        tertiaryBorderColor: v("--blue"),
        lineColor: v("--muted"),
        textColor: v("--ink"),
        clusterBkg: v("--paper"),
        clusterBorder: v("--rule-strong"),
        edgeLabelBackground: v("--surface"),
        noteBkgColor: v("--amber-wash"),
        noteBorderColor: v("--amber-bright"),
        actorBkg: v("--surface"),
        actorBorder: v("--navy"),
      },
    });
    return m;
  });
  return api;
}

export function renderMermaid(source: string): Promise<string> {
  const job = queue.then(async () => {
    const m = await load();
    const id = `mmd-${++counter}`;
    try {
      const { svg } = await m.render(id, source);
      return svg;
    } catch (e) {
      document.getElementById(id)?.remove();
      document.getElementById(`d${id}`)?.remove();
      log.error("diagram failed to render", e);
      throw e;
    }
  });
  queue = job.catch(() => undefined);
  return job;
}
