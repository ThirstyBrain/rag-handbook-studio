import type { RenderContext } from "@/shared/markdown/render";
import { getHandbook } from "./handbook";

let ctx: RenderContext | null = null;

/** What the Markdown renderer needs to know to turn mentions into links. */
export function handbookRenderContext(): RenderContext {
  if (ctx) return ctx;
  const hb = getHandbook();
  ctx = {
    chapterSlugs: new Map(hb.chapters.map((c) => [c.number, c.slug])),
    adrIds: new Set(hb.adrs.map((a) => a.id)),
    exercises: new Set(hb.exercises.map((e) => e.file)),
    skipH1: true,
  };
  return ctx;
}
