import { getHandbook } from "@/content/handbook";
import { STAGES } from "./stages";

describe("architecture stages reference real handbook content", () => {
  const hb = getHandbook();
  it("every diagram file exists", () => {
    for (const s of STAGES) for (const d of s.diagrams) expect(hb.diagrams.has(d), `${s.id}: ${d}`).toBe(true);
  });
  it("every ADR exists", () => {
    for (const s of STAGES) for (const a of s.adrs) expect(hb.adrs.some((x) => x.id === a), `${s.id}: ${a}`).toBe(true);
  });
  it("every chapter is in the table of contents", () => {
    for (const s of STAGES) for (const n of s.chapters) expect(hb.entries.some((e) => e.number === n), `${s.id}: ${n}`).toBe(true);
  });
  it("stage ids are unique", () => {
    expect(new Set(STAGES.map((s) => s.id)).size).toBe(STAGES.length);
  });
});
