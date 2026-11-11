import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { RouterProvider } from "@/shared/router/router";
import { addSink } from "@/shared/analytics/track";
import { ExercisePanel } from "@/features/exercises/ExercisePanel";
import GlossaryPage from "@/features/glossary/GlossaryPage";
import PlaygroundPage from "@/features/playground/PlaygroundPage";
import ChapterPage from "@/features/reader/ChapterPage";
import HandbookIndexPage from "@/features/handbook/HandbookIndexPage";
import DecisionsPage from "@/features/decisions/DecisionsPage";
import { getHandbook } from "@/content/handbook";

const wrap = (ui: ReactNode) => render(<RouterProvider>{ui}</RouterProvider>);

describe("ExercisePanel", () => {
  it("shows the captured output first and switches to the source with the keyboard", () => {
    wrap(<ExercisePanel file="ch10_query_transform.py" />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual(["Output", "Source", "_toy_ir.py"]);
    expect(tabs[0]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Captured terminal output").textContent).toContain("python -I docs/exercises/ch10_query_transform.py");

    fireEvent.keyDown(tabs[0]!, { key: "ArrowRight" });
    expect(screen.getAllByRole("tab")[1]).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Python source").textContent).toContain("sys.path.insert");
  });

  it("offers a tab per cited variant run", () => {
    wrap(<ExercisePanel file="ch12_reranking.py" args="--mutants" />);
    const selected = screen.getAllByRole("tab").find((t) => t.getAttribute("aria-selected") === "true");
    expect(selected?.textContent).toBe("Output --mutants");
  });

  it("renders nothing for an unknown file", () => {
    const { container } = wrap(<ExercisePanel file="nope.py" />);
    expect(container.textContent).toBe("");
  });
});

describe("GlossaryPage", () => {
  it("filters by text and shows an empty state when nothing matches", () => {
    wrap(<GlossaryPage />);
    const total = getHandbook().glossary.length;
    expect(screen.getByText(`${total} terms`)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filter glossary"), { target: { value: "reciprocal" } });
    expect(screen.queryByText(`${total} terms`)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filter glossary"), { target: { value: "qqqzzz" } });
    expect(screen.getByText("No term matches")).toBeInTheDocument();
  });

  it("filters by letter and emits an analytics event", () => {
    const events: string[] = [];
    const off = addSink((e) => events.push(e.name));
    wrap(<GlossaryPage />);
    fireEvent.click(screen.getByRole("button", { name: "B" }));
    const group = screen.getByRole("heading", { level: 2, name: "B" });
    expect(group).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "R" })).not.toBeInTheDocument();
    expect(events).toContain("glossary_filter");
    off();
  });
});

describe("PlaygroundPage", () => {
  it("shows nDCG for a judged query and hides it for a free query", async () => {
    wrap(<PlaygroundPage />);
    expect(screen.getByText("Quality against the exercise's judgements")).toBeInTheDocument();
    await act(async () => {
      fireEvent.change(screen.getByLabelText("Query"), { target: { value: "rotate api keys" } });
    });
    expect(screen.getByText(/has no relevance judgements/)).toBeInTheDocument();
    const lexical = screen.getByRole("heading", { name: "Keyword (BM25)" }).parentElement!;
    expect(within(lexical).getByText("d8")).toBeInTheDocument();
  });

  it("shows an empty state for an empty query", async () => {
    wrap(<PlaygroundPage />);
    await act(async () => {
      fireEvent.change(screen.getByLabelText("Query"), { target: { value: "" } });
    });
    expect(screen.getByText("Type a query to run the pipeline")).toBeInTheDocument();
  });

  it("resets parameters to the script defaults", async () => {
    wrap(<PlaygroundPage />);
    const reset = screen.getByRole("button", { name: "Reset to script" });
    expect(reset).toBeDisabled();
    await act(async () => {
      fireEvent.change(screen.getByLabelText("RRF constant k"), { target: { value: "5" } });
    });
    expect(reset).toBeEnabled();
    await act(async () => fireEvent.click(reset));
    expect(reset).toBeDisabled();
  });
});

describe("ChapterPage", () => {
  it("renders a real chapter with its outline, evidence and pager", () => {
    wrap(<ChapterPage params={{ slug: "09-hybrid-search" }} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Hybrid Search");
    expect(screen.getByRole("heading", { level: 2, name: /9\.4 Core Concepts/ })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Previous and next chapter" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /Highlight claims by evidence/ })).toBeInTheDocument();
  });

  it("dims other evidence when one kind is highlighted", () => {
    const { container } = wrap(<ChapterPage params={{ slug: "09-hybrid-search" }} />);
    const group = screen.getByRole("group", { name: /Highlight claims by evidence/ });
    fireEvent.click(within(group).getByRole("button", { name: /Executed/ }));
    expect(container.querySelector(".prose")).toHaveAttribute("data-evidence-focus", "X");
  });

  it("shows the not-found page for an unknown chapter", () => {
    wrap(<ChapterPage params={{ slug: "99-nope" }} />);
    expect(screen.getByText("No page at this address")).toBeInTheDocument();
  });
});

describe("HandbookIndexPage", () => {
  it("lists written and planned chapters and filters them", () => {
    const hb = getHandbook();
    // The handbook grows; pick whichever chapter is still unwritten today.
    const planned = hb.entries.find((e) => !hb.chapters.some((c) => c.number === e.number));
    wrap(<HandbookIndexPage />);
    if (planned) expect(screen.getByText(planned.title)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Written" }));
    if (planned) expect(screen.queryByText(planned.title)).not.toBeInTheDocument();
    expect(screen.getByText("Hybrid Search")).toBeInTheDocument();
  });
});

describe("DecisionsPage", () => {
  it("renders an ADR with its decision anatomy", () => {
    wrap(<DecisionsPage params={{ id: "ADR-004" }} />);
    expect(screen.getByRole("heading", { level: 2, name: /Retrieval Architecture/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Decision/ })).toBeEnabled();
  });
});
