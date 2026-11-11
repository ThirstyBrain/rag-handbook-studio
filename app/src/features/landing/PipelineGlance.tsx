import { Fragment } from "react";
import { Link } from "@/shared/router/router";
import { Icon, type IconName } from "@/shared/ui/Icon";

/**
 * "RAG Architecture at a Glance": the request path as eight nodes. Each node opens the matching
 * stage of the architecture map, so the diagram is navigation, not decoration.
 */
const NODES: { label: string; icon: IconName; stage: string; tone?: "done" }[] = [
  { label: "Documents", icon: "file", stage: "ingest" },
  { label: "Ingestion", icon: "gear", stage: "ingest" },
  { label: "Chunking", icon: "cubes", stage: "chunk" },
  { label: "Embedding", icon: "embed", stage: "embed" },
  { label: "Search", icon: "search", stage: "retrieve" },
  { label: "Reranking", icon: "star", stage: "rerank" },
  { label: "LLM", icon: "bolt", stage: "generate" },
  { label: "Grounded Response", icon: "check", stage: "generate", tone: "done" },
];

export function PipelineGlance() {
  return (
    <div className="glance">
      <p className="glance__badge">
        <Icon name="layers" size={18} />
        RAG Architecture at a Glance
      </p>
      <ol className="glance__flow" aria-label="RAG request path. Each step opens its stage on the architecture map.">
        {NODES.map((n, i) => (
          <Fragment key={n.label}>
            <li className="glance__step" style={{ "--i": i } as React.CSSProperties}>
              <Link href={`/architecture#${n.stage}`} className={`glance__node${n.tone ? ` glance__node--${n.tone}` : ""}`}>
                <span className="glance__icon">
                  <Icon name={n.icon} size={22} />
                </span>
                <span className="glance__label">{n.label}</span>
              </Link>
            </li>
            {i < NODES.length - 1 && (
              <li className="glance__arrow" aria-hidden="true" style={{ "--i": i } as React.CSSProperties}>
                <svg viewBox="0 0 24 10" width="22" height="10">
                  <path className="glance__wire" d="M1 5h18" />
                  <path d="M16 1.5 20.5 5 16 8.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </li>
            )}
          </Fragment>
        ))}
      </ol>
    </div>
  );
}
