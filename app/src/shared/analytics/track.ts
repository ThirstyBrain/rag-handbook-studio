/**
 * Vendor-neutral, typed analytics. Events are buffered and re-dispatched as `rag:analytics`
 * DOM events; nothing leaves the browser unless a sink is registered with `addSink`.
 */
export type AnalyticsEvent =
  | { name: "page_view"; path: string }
  | { name: "search_opened"; source: "shortcut" | "button" }
  | { name: "search_selected"; kind: string; target: string; rank: number }
  | { name: "chapter_completed"; chapter: number }
  | { name: "code_copied"; language: string }
  | { name: "exercise_tab"; file: string; tab: string }
  | { name: "playground_query"; query: string; preset: boolean }
  | { name: "architecture_stage"; stage: string }
  | { name: "diagram_expanded"; file: string }
  | { name: "glossary_filter"; letter: string };

type Sink = (e: AnalyticsEvent & { at: number }) => void;
const sinks = new Set<Sink>();
const buffer: (AnalyticsEvent & { at: number })[] = [];
const MAX_BUFFER = 200;

export function track(event: AnalyticsEvent): void {
  const entry = { ...event, at: Date.now() };
  buffer.push(entry);
  if (buffer.length > MAX_BUFFER) buffer.shift();
  sinks.forEach((s) => s(entry));
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("rag:analytics", { detail: entry }));
}

export function addSink(sink: Sink): () => void {
  sinks.add(sink);
  return () => sinks.delete(sink);
}

export const recentEvents = () => [...buffer];
