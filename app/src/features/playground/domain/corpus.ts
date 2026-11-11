/**
 * The toy corpus and relevance judgements from `docs/exercises/ch09_hybrid_search.py` (Part C),
 * copied verbatim. engine.test.ts checks that this copy still matches the script in the handbook,
 * so an edit to the exercise fails the test instead of silently diverging.
 */
export const CORPUS: Record<string, string> = {
  d1: "ADR-017 rejected Kafka for the ingestion queue because of operational overhead.",
  d2: "Runbook: error E-4471 means the vector index is rebuilding. Wait for the rebuild to finish.",
  d3: "Parental leave policy: employees receive 16 weeks of paid leave.",
  d4: "Contractors are not covered by the parental leave policy unless their contract says otherwise.",
  d5: "The ingestion queue uses Azure Service Bus with dead-letter handling.",
  d6: "Index rebuilds are triggered when the embedding model changes.",
  d7: "Expense policy: meals above 50 euros require a receipt.",
  d8: "Security runbook: rotate API keys every 90 days.",
};

export const QRELS: Record<string, Record<string, number>> = {
  "why did we drop kafka": { d1: 2, d5: 1 },
  "E-4471": { d2: 2, d6: 1 },
  "contractor leave": { d4: 2, d3: 1 },
  "dead letter queue": { d5: 2 },
};

export const SOURCE_FILE = "ch09_hybrid_search.py";
