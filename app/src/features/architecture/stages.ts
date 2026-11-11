/**
 * The architecture map's stages. This file is the one piece of editorial curation in the app:
 * it says which handbook chapters, diagram files and ADRs belong to each stage of a RAG system.
 * All descriptive text shown for a stage is pulled from those chapters at runtime.
 * Unknown chapter numbers, diagram files or ADR ids are dropped (and caught by stages.test.ts).
 */
export type Lane = "offline" | "online" | "cross";

export interface Stage {
  id: string;
  name: string;
  lane: Lane;
  /** Primary chapter first; its problem statement supplies the stage description. */
  chapters: number[];
  diagrams: string[];
  adrs: string[];
}

export const STAGES: Stage[] = [
  { id: "ingest", name: "Ingest and parse", lane: "offline", chapters: [3], diagrams: ["03-ingestion-pipeline.mmd", "03-document-lifecycle.mmd"], adrs: ["ADR-001"] },
  { id: "chunk", name: "Chunk", lane: "offline", chapters: [4, 14], diagrams: ["04-chunking-strategy-selection.mmd", "14-hierarchy-strategies.mmd"], adrs: ["ADR-003"] },
  { id: "embed", name: "Embed", lane: "offline", chapters: [2, 5], diagrams: ["02-embedding-generation.mmd"], adrs: ["ADR-002"] },
  { id: "index", name: "Index and store", lane: "offline", chapters: [5], diagrams: ["05-vector-store-architecture.mmd", "05-vector-store-selection.mmd"], adrs: ["ADR-001"] },
  { id: "transform", name: "Transform the query", lane: "online", chapters: [10, 11], diagrams: ["10-query-transform-pipeline.mmd", "10-transform-selection.mmd", "11-multi-query-fanout.mmd"], adrs: ["ADR-007"] },
  { id: "filter", name: "Filter and authorise", lane: "online", chapters: [13, 8], diagrams: ["13-filter-compilation.mmd", "13-filter-strategy-decision.mmd", "05-filtered-search-strategies.mmd"], adrs: ["ADR-009", "ADR-006"] },
  { id: "retrieve", name: "Hybrid retrieval", lane: "online", chapters: [9, 6], diagrams: ["09-hybrid-search-flow.mmd", "06-retrieval-workflow.mmd"], adrs: ["ADR-004"] },
  { id: "rerank", name: "Rerank", lane: "online", chapters: [12], diagrams: ["12-retrieve-rerank-pipeline.mmd", "12-reranker-architectures.mmd"], adrs: ["ADR-008"] },
  { id: "assemble", name: "Assemble context", lane: "online", chapters: [14, 6], diagrams: ["14-parent-child-retrieval.mmd"], adrs: ["ADR-003"] },
  { id: "generate", name: "Generate and cite", lane: "online", chapters: [7, 1], diagrams: ["07-query-sequence.mmd", "07-logical-architecture.mmd", "01-llm-vs-rag.mmd"], adrs: ["ADR-005"] },
  { id: "agent", name: "Agentic loop", lane: "online", chapters: [15, 11], diagrams: ["15-agent-control-loop.mmd", "15-corrective-retrieval.mmd", "11-iterative-retrieval-loop.mmd"], adrs: ["ADR-010"] },
  { id: "isolation", name: "Tenant isolation and trust", lane: "cross", chapters: [8, 7], diagrams: ["08-enterprise-isolation-architecture.mmd", "08-identity-propagation.mmd", "07-trust-failure-boundaries.mmd", "08-ha-dr-topology.mmd", "07-deployment-architecture.mmd"], adrs: ["ADR-006"] },
  { id: "evaluate", name: "Evaluate and observe", lane: "cross", chapters: [18, 19], diagrams: [], adrs: [] },
];

export const LANE_LABEL: Record<Lane, string> = {
  offline: "Indexing path, runs ahead of time",
  online: "Query path, runs per request",
  cross: "Applies to every stage",
};
