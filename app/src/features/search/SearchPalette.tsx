import { useEffect, useId, useMemo, useRef, useState } from "react";
import { getHandbook } from "@/content/handbook";
import { track } from "@/shared/analytics/track";
import { useRouter } from "@/shared/router/router";
import { buildSearchDocs, SearchIndex, type SearchHit, type SearchKind } from "./searchIndex";
import "./search.css";

let index: SearchIndex | null = null;
const getIndex = () => (index ??= new SearchIndex(buildSearchDocs(getHandbook())));

const KIND_LABEL: Record<SearchKind, string> = {
  chapter: "Chapter",
  section: "Section",
  term: "Glossary",
  decision: "Decision",
  exercise: "Exercise",
  reference: "Source",
};

const FILTERS: { id: SearchKind | "all"; label: string }[] = [
  { id: "all", label: "Everything" },
  { id: "section", label: "Sections" },
  { id: "term", label: "Glossary" },
  { id: "decision", label: "Decisions" },
  { id: "exercise", label: "Exercises" },
  { id: "reference", label: "Sources" },
];

const SUGGESTIONS = ["reciprocal rank fusion", "row level security", "HNSW", "cross-encoder", "chunk overlap", "prompt injection"];

export default function SearchPalette({ initialQuery, onClose }: { initialQuery: string; onClose: () => void }) {
  const { navigate } = useRouter();
  const [query, setQuery] = useState(initialQuery);
  const [filter, setFilter] = useState<SearchKind | "all">("all");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const listId = useId();

  useEffect(() => {
    const d = dialogRef.current;
    d?.showModal?.();
    inputRef.current?.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  const results = useMemo<SearchHit[]>(() => {
    const all = getIndex().search(query, 60);
    return (filter === "all" ? all : all.filter((h) => h.doc.kind === filter || (filter === "section" && h.doc.kind === "chapter"))).slice(0, 30);
  }, [query, filter]);

  useEffect(() => setActive(0), [query, filter]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  const go = (hit: SearchHit, rank: number) => {
    track({ name: "search_selected", kind: hit.doc.kind, target: hit.doc.href, rank });
    onClose();
    navigate(hit.doc.href);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(results.length - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      go(results[active]!, active);
    }
  };

  const activeId = results[active] ? `${listId}-${active}` : undefined;

  return (
    <dialog ref={dialogRef} className="palette" aria-label="Search the handbook" onClose={onClose} onClick={(e) => e.target === dialogRef.current && onClose()}>
      <div className="palette__panel" onKeyDown={onKeyDown}>
        <div className="palette__bar">
          <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" className="palette__icon">
            <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            ref={inputRef}
            className="palette__input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chapters, sections, terms, decisions"
            role="combobox"
            aria-expanded={results.length > 0}
            aria-controls={listId}
            aria-activedescendant={activeId}
            aria-autocomplete="list"
            spellCheck={false}
          />
          <button type="button" className="kbd palette__esc" onClick={onClose}>
            Esc
          </button>
        </div>

        <div className="palette__filters" role="group" aria-label="Filter results">
          {FILTERS.map((f) => (
            <button key={f.id} type="button" className="palette__filter" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
            </button>
          ))}
        </div>

        {query.trim() === "" ? (
          <div className="palette__idle">
            <p className="palette__hint">Searches {getIndex().size.toLocaleString()} passages across the written chapters, glossary, decisions, exercises and sources. Try:</p>
            <div className="palette__suggest">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="chip" onClick={() => setQuery(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : results.length === 0 ? (
          <div className="palette__idle">
            <p className="palette__none">Nothing matches “{query}”.</p>
            <p className="palette__hint">Every word must appear somewhere in a passage. Remove a word, or check the spelling of identifiers such as ts_rank_cd.</p>
          </div>
        ) : (
          <ul ref={listRef} id={listId} className="palette__list" role="listbox" aria-label="Search results">
            {results.map((hit, i) => (
              <li
                key={hit.doc.id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                data-index={i}
                className="palette__item"
                onMouseMove={() => setActive(i)}
                onClick={() => go(hit, i)}
              >
                <span className={`palette__kind palette__kind--${hit.doc.kind}`}>{KIND_LABEL[hit.doc.kind]}</span>
                <span className="palette__main">
                  <span className="palette__title">{hit.doc.title}</span>
                  <span className="palette__context">{hit.doc.context}</span>
                  <Snippet snippet={hit.snippet} />
                </span>
              </li>
            ))}
          </ul>
        )}

        <div className="palette__foot" aria-hidden="true">
          <span>
            <kbd className="kbd">↑</kbd> <kbd className="kbd">↓</kbd> to move
          </span>
          <span>
            <kbd className="kbd">Enter</kbd> to open
          </span>
          <span>
            <kbd className="kbd">Esc</kbd> to close
          </span>
        </div>
      </div>
    </dialog>
  );
}

function Snippet({ snippet }: { snippet: SearchHit["snippet"] }) {
  const parts: React.ReactNode[] = [];
  let pos = 0;
  snippet.marks.forEach(([a, b], i) => {
    if (a > pos) parts.push(snippet.text.slice(pos, a));
    parts.push(<mark key={i}>{snippet.text.slice(a, b)}</mark>);
    pos = b;
  });
  parts.push(snippet.text.slice(pos));
  return <span className="palette__snippet">{parts}</span>;
}
