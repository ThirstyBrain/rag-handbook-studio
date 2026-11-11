# System Design Interview Guide

> GENERATED FILE. Source of truth: `docs/chapters/32-system-design-interview-preparation.md`. Rebuild with `python -I scripts/build-interview-pack.py`.

## 32.4 Core Concepts: A Method for the Session

### 32.4.1 The seven-step frame **[E]**

| Step | Minutes | What you produce | Typical trap |
|---|---|---|---|
| 1. Clarify | 5 | Users, corpus size and change rate, question types, permissions, latency and cost limits, regions, regulatory context | Drawing before asking |
| 2. Constrain | 3 | Non-negotiables (tenant isolation, residency, citation rules, budget), stated as testable requirements | Leaving "secure" vague |
| 3. Size | 4 | Order-of-magnitude chunks, vectors, QPS, tokens per query, monthly cost, labelled as assumptions **[A]** | Precise numbers from nowhere |
| 4. Draw | 8 | Two paths: offline ingestion and online query, with trust boundaries | One box called "RAG" |
| 5. Deep-dive | 15 | The two or three hardest parts for this scenario (filtering, freshness, evaluation) | Spreading evenly over everything |
| 6. Fail | 6 | Failure modes, degradation order, what must never degrade (security) | Only happy path |
| 7. Evolve | 4 | What you would measure, what would change the decision | Declaring the design final |

### 32.4.2 Clarifying questions that change the design **[E]**

Each question below maps to a pattern decision in Chapter 30.

- **Question type.** Lookups, comparisons, multi-document synthesis, aggregates, "how many", whole-corpus themes? Aggregates point to text-to-SQL (Chapter 29); corpus-level themes to summary structures (Chapter 14); dependent facts to iterative retrieval (Chapter 11).
- **Corpus size and churn.** A corpus that fits in a context window may not need retrieval at all, and Chapter 30 gives the break-even arithmetic **[X]**.
- **Permissions.** Who may see which document, how often does that change, and who is the source of truth (Chapters 8, 24)?
- **Tenancy.** How many tenants, how skewed, any residency or per-tenant key needs (Chapters 5, 8, 13)?
- **Correctness cost.** What does a wrong answer cost? That sets abstention, citation and human-approval rules (Chapters 18, 25).
- **Freshness.** How stale may an answer be, and how stale may a permission be (Chapter 24)?
- **Latency and cost.** The p95 budget and the cost per query decide whether reranking, query rewriting or agents are affordable (Chapters 12, 20).

### 32.4.3 The security boundary, stated early **[E]**

State where authorization is enforced: in code that receives an immutable identity, in the database (forced row-level security under a restricted role, Chapter 8 and ADR-013), and again after retrieval. State that retrieved text is untrusted and the model can be persuaded, so the controls must not rely on the prompt (Chapter 22). Saying this in minute 10 changes the interviewer's questions for the rest of the hour.

### 32.4.4 Sizing without invented numbers **[E]**

Give the formula and the assumption, not just the result. For example: vectors = documents × chunks per document; memory ≈ vectors × dimensions × bytes per dimension plus index overhead; tokens per query = static prefix + retrieved context + output, where retrieved context and output dominate and only the static prefix is cacheable (Chapter 20). Label the inputs **[A]** and offer to replace them with measurements.

## 32.5 The Scoring Rubric

Score each scenario 0–3 on each dimension (0 = absent, 1 = named, 2 = reasoned, 3 = reasoned with evidence and a reversal condition). A practice session is a self-score plus the single weakest dimension to work on **[E]**.

| Dimension | A 3-level answer looks like |
|---|---|
| Requirements | Asks questions whose answers change the design, and restates the constraints as tests |
| Architecture fit | Smallest design that meets the requirements; rejects at least two alternatives with reasons |
| Retrieval depth | Chooses chunking, index, filtering and fusion for this corpus and explains the recall–filter interaction |
| Security and isolation | Identity propagation, database enforcement, post-retrieval re-check, untrusted-content handling, deletion |
| Evaluation | Separates retrieval from generation, has a golden set with hostile and unanswerable cases, gates releases |
| Operations | SLOs, degradation order, cost model, incident response, rollback |
| Trade-offs and evolution | States what is given up, what would change the decision, and what to measure first |

## 32.6 Scenarios

Each scenario lists the prompt, the questions to ask first, a model architecture, the trade-offs, the failure modes, interviewer probes, a scoring focus, and the chapters that carry the evidence. The model answers are compact on purpose: they are what a strong candidate says in the *deep-dive* step, not a transcript. Numbers marked **[X]** are results from this repository's exercises and come from synthetic or constructed data, not benchmarks.

### SD-01 — Internal HR Policy Assistant

**Prompt.** An 8,000-person company wants an assistant that answers HR policy questions from about 400 policy documents, with citations. One country, one language.

**Clarify first.** How large is the corpus in tokens, how often do policies change, are any documents restricted by role or country, what happens when the answer is not in the policy (escalate to HR?), and what is the budget?

**Model architecture.** Test the simplest option first: a corpus this small may fit in a context window, so compare long-context against retrieval on cost, latency and accuracy using the break-even arithmetic of Chapter 30 **[X]**. The evidence reviewed says models use long contexts unevenly [S19] and that retrieval is much cheaper than long-context even when long-context is more accurate on average [S21]. If retrieval wins: structure-aware chunking with heading paths (Chapter 4), one embedding space, a single-store hybrid retrieval with Postgres and a lexical leg (Chapter 9), citation validation after generation (Chapter 7), and an abstention path to a human.

**Trade-offs.** Long-context is simpler but pays per query and degrades on position; retrieval adds an index and an ingestion path but is cheaper per query and gives citations that can be verified [S19, S21]. Accept a periodic re-index for freshness. Reconsider if the corpus grows by an order of magnitude or restricted content appears.

**Failure modes.** Stale policy served after an update; a table row separated from its header by chunking (Chapter 4); an answer with a citation that does not support it (Chapter 18 citation checks); a confident answer where the policy is silent.

**Probes.** "Why not just paste everything into the prompt?" "How do you know the answer is grounded?" "What if two policies conflict?"

**Scoring focus.** Architecture fit (not over-building), evaluation.

**Draws on.** Chapters 1, 4, 7, 9, 18, 30.

### SD-02 — Multi-Tenant SaaS Knowledge Assistant

**Prompt.** A B2B SaaS product adds an assistant over each customer's uploaded documents. There are 10,000 tenants; a few have millions of chunks, most have a few thousand.

**Clarify first.** Tenant size distribution, residency, any per-tenant encryption keys, noisy-neighbour tolerance, delete-on-offboarding requirement, and whether tenants may share content.

**Model architecture.** Pick the tenancy topology from the size distribution: a shared index with a mandatory tenant predicate for the many small tenants, and partitioning or dedicated storage for the few large ones (Chapters 5, 8, 13). Enforce isolation in the database with forced row-level security under a restricted role, with fail-closed identity (ADR-013, Chapter 8), and test that the filter is applied inside each retrieval leg before the limit. Filter selectivity decides retrieval quality: on a 10% filter an HNSW index returned 4.10 of 10 results by default and 10.00 with iterative scan, 1% and 0.1% were rescued by an exact plan, and a generic prepared-statement plan reversed that rescue to 0.45 and 0.00 of 10 **[X]** (synthetic data, PostgreSQL 16, Chapter 13). List partitioning pruned a tenant query to one partition and kept a 10% tenant at 10 of 10 **[X]**.

**Trade-offs.** A shared index is cheapest and simplest and carries the largest blast radius if a filter is wrong; dedicated indexes cost more and isolate better. The identity setting that row-level security reads must itself be protected: in this project the application role could change its tenant identity with `set_config`, an open finding (OI-069, Chapter 29).

**Failure modes.** A filter applied after the candidate limit returns too few or wrong results; a cache keyed without the tenant leaks across tenants (Chapter 7); a large tenant degrades a small one; deletion leaves vectors behind.

**Probes.** "Show me where cross-tenant retrieval is made impossible." "What does your monitoring say when a tenant gets 3 of 10 results?" "How do you offboard a tenant?"

**Scoring focus.** Security and isolation, retrieval depth.

**Draws on.** Chapters 5, 7, 8, 13, 29; ADR-013; OI-069.

### SD-03 — Permission-Aware Enterprise Search Across Wikis and Drives

**Prompt.** Build an assistant over Confluence, SharePoint and a shared drive. Users must only see answers derived from documents they may read. Permissions change daily.

**Clarify first.** Which sources, synced or federated access, how stale a permission may be, how groups are nested, what to do with content whose permissions cannot be mapped, and the audit requirement.

**Model architecture.** Per source, choose synced or federated (Chapter 24). Map source permissions conservatively and exclude what cannot be represented. Store group principals and resolve membership at query time, so a membership change takes effect without re-indexing every chunk. Treat ACL-only, inherited and group changes as first-class events, apply changes idempotently, and run reconciliation as a fallback. Bound permission staleness and decide per source class whether to fail closed (Chapter 24). Compile the policy into a retrieval filter and prove the equivalence by test, with a post-retrieval re-check (Chapter 8) **[X]**.

**Trade-offs.** Synced is fast and private to query but lags and duplicates permission data; federated is fresh but slower and limited by the source's search. My simulation showed an order-of-magnitude difference in exposure between designs **[X]** under my parameters (Chapter 24, synthetic).

**Failure modes.** Revocation lag exposes a document; an inherited folder permission is missed; a connector re-sync resurrects deleted items; derived summaries outlive their sources (Chapter 30).

**Probes.** "A user is removed from a group at 9:00. When does the assistant stop quoting their documents?" "How do you prove it?"

**Scoring focus.** Security and isolation, operations.

**Draws on.** Chapters 8, 24, 30.

### SD-04 — Public Customer Support Chatbot

**Prompt.** A retailer wants a website chatbot to deflect support tickets, answering from help articles and order policies.

**Clarify first.** Which intents are high risk (refunds, legal, safety), what the bot may commit to, the handoff channel, disclosure obligations, the public audience's hostility, and how success is defined.

**Model architecture.** Treat the bot as a decision policy with a model inside it (Chapter 25). Disclose AI use first; route high-risk intents to humans always; set confidence thresholds per intent by expected cost; allow commitments only as verbatim quotations of the cited, authoritative policy; hand off with context through a path that always works. Apply Chapter 22's controls with a hostile audience: input and output policy, no tools with side effects without approval, rate limits. Roll out through agent assist and shadow mode with a kill switch.

**Trade-offs.** Higher thresholds raise safety and cost handoffs; in my simulation containment overstated verified resolution by 21 points and the optimal threshold was interior **[X]** (synthetic data, assumed calibration, Chapter 25). Measure verified resolution, not containment.

**Failure modes.** The bot invents a policy and the customer relies on it (the Air Canada case is discussed in Chapter 25 from commentary only; the decision itself was not read **[N]**); prompt injection through the chat; handoff that loops.

**Probes.** "What is your containment number and why do you distrust it?" "What does the bot do when the policy is silent?"

**Scoring focus.** Evaluation, security, trade-offs.

**Draws on.** Chapters 18, 22, 25.

### SD-05 — Research Assistant With Trustworthy Citations

**Prompt.** Lawyers or scientists want answers with references to papers or cases. A fabricated reference is unacceptable.

**Clarify first.** Closed or open corpus, whether the model may cite outside the index, licensing of the content, tolerance for "I cannot support that", and how citations are checked today.

**Model architecture.** Make fabrication structurally impossible: cite only retrieved identifiers and render bibliographies from index metadata. For anything the model produces outside that, verify by DOI lookup with metadata comparison, fuzzy matching with an ambiguity band, field-level error reporting and retraction checks (Chapter 26). Verify quotations against the source text and check claim support. Retrieve with hybrid search and rerank for precision (Chapters 9, 12), preserve page and section locators from extraction, and route confidential or licensed material (Chapter 26).

**Trade-offs.** Verification adds latency and a human review queue (9.6% routed to a human in my synthetic harness **[X]**). Measured fabrication in model-written citations comes from 2023 models and was high (Chapter 26); newer models need re-measurement **[N]**.

**Failure modes.** A real paper cited for a claim it does not make; a retracted paper cited; an exact-match verifier rejecting correct citations on formatting alone **[X]**.

**Probes.** "How do you detect a citation that exists but does not support the claim?" "Who sees the verifier's rejections?"

**Scoring focus.** Evaluation, retrieval depth.

**Draws on.** Chapters 9, 12, 18, 26.

### SD-06 — Codebase Assistant

**Prompt.** Engineers want to ask questions about a 5-million-line monorepo and get answers with file and line citations.

**Clarify first.** Languages, repository permissions, update frequency, whether answers may suggest code, secret and licence policy, and IDE versus chat.

**Model architecture.** Index units that respect syntax (functions and classes) with context headers; add a symbol index for structural questions such as "who calls this"; assemble context under a budget with file and line citations; index incrementally on commit; enforce repository-level access control; scan for secrets and licences; treat generated code and suggested dependencies as untrusted (Chapter 27). On this repository's own Python, line windows cut through functions in 73.7% of chunks against 3.0% for AST units; but the retrieval advantage of AST chunking was not distinguishable from chance on 34 to 41 docstring-derived queries **[X]** (small, single-repository, lexical measurement). So the structural case is established and the retrieval case is open.

**Trade-offs.** Language-specific parsing costs maintenance; a symbol index answers structural questions exactly but needs its own freshness. A leakage check showed how a careless evaluation can look perfect **[X]**.

**Failure modes.** Stale index after a force-push; a secret in a chunk returned to a user without access; a hallucinated API.

**Probes.** "How would you evaluate this without leaking the answer into the query?" "How do you handle a monorepo with per-directory ownership?"

**Scoring focus.** Retrieval depth, evaluation.

**Draws on.** Chapters 4, 18, 27.

### SD-07 — Natural-Language Questions Over the Data Warehouse

**Prompt.** Business users want to ask "revenue by region last quarter" in English.

**Clarify first.** Are there governed metrics, how many tables, who may see which rows and columns, tolerance for a wrong number, and who owns the semantic layer.

**Model architecture.** Prefer governed metrics over free SQL. Ground generation in retrieved schema and metric definitions. Execute as a restricted role with column grants, forced row-level security, a read-only transaction, a timeout and a row cap. Treat text filters as hygiene only. Protect the identity setting that row-level security reads. Compute every number in SQL, never in the model. Evaluate execution accuracy on several distinguishing datasets rather than by string match (Chapter 29). On real PostgreSQL the guard stopped all 21 attacks, a text pre-check passed 10 of them, and execution accuracy agreed with the truth 100% of the time only when run on two tenants **[X]**.

**Trade-offs.** Governed metrics limit flexibility and win on correctness; free SQL is flexible and needs the strongest guard. Aggregates are a text-to-SQL problem, not a retrieval problem (Chapter 30).

**Failure modes.** A plausible query that joins wrongly and returns a wrong number; a SQL attack that changes the tenant setting; a runaway query.

**Probes.** "Why execute the SQL during evaluation?" "Where does the model's authority end?"

**Scoring focus.** Security, evaluation.

**Draws on.** Chapters 22, 29, 30; OI-069.

### SD-08 — Multimodal Technical-Manual Search

**Prompt.** Field engineers search PDF manuals full of diagrams, tables and photos.

**Clarify first.** Share of content in figures and tables, need to cite page regions, device constraints, languages, and the cost budget.

**Model architecture.** Choose per content class among extraction, verbalisation and direct or page-level embeddings. Keep tables structured, link figures to captions and referencing text, cite regions, budget visual tokens, and send image regions only when needed. Treat all derived text as untrusted and labelled, sandbox media parsing, evaluate each modality separately (Chapter 28). In my example four page images cost 2.2 times the extracted text, and caption linking reached 99.0% against 57.7% for a naive baseline on synthetic pages **[X]**.

**Trade-offs.** Direct visual embedding preserves layout and costs more tokens and index size; verbalisation is cheap and lossy. Choose by measured query class **[E]**.

**Failure modes.** A table's units lost in extraction; a figure matched to the wrong caption; a transcript hallucinating speech; an image carrying injected instructions.

**Probes.** "When would you not use a vision model?" "How do you cite part of a page?"

**Scoring focus.** Retrieval depth, trade-offs.

**Draws on.** Chapters 3, 22, 28.

### SD-09 — The Bill Doubled

**Prompt.** Monthly model and infrastructure cost has doubled with no change in traffic. Find and fix it.

**Clarify first.** Cost breakdown by component, token counts per request over time, cache hit rate, recent releases, and quality constraints.

**Model architecture.** Start with measurement. Model the token bill: retrieved context and output dominate and only the static prefix is cacheable (Chapter 20). Look for a changed context size (top-K raised, longer chunks), disabled prompt caching, query rewriting or multi-query fan-out added to every request (Chapter 11), a rerank depth increase, retries multiplying calls (Chapter 21), or an agent loop without a budget (Chapter 15). Fix by routing cheap models to easy queries, caching, trimming K using evaluation, and budgets in the gateway (ADR-012).

**Trade-offs.** Every cut is a retrieval or generation change and needs the golden-set check: precision, dimension and index changes are retrieval changes that need evaluation (Chapter 20). Reconsider routing when its error cost exceeds its savings.

**Failure modes.** Cutting K and losing recall under filters; caching a response across tenants; a retry storm.

**Probes.** "What do you look at first?" "How do you know the cheaper path did not hurt quality?"

**Scoring focus.** Operations, evaluation.

**Draws on.** Chapters 11, 15, 18, 20, 21.

### SD-10 — Quality Dropped After an Embedding Upgrade

**Prompt.** A team upgraded to a newer embedding model and users report worse answers.

**Clarify first.** Was the whole corpus re-embedded, are query and document vectors from the same model, what changed in dimensions or normalisation, and what evaluation existed before.

**Model architecture.** Embedding models are versioned schema: record the identity, plan migration, measure drift (Chapter 2). The first hypothesis is an embedding-space mismatch (queries from the new model against documents from the old), which the gateway's embedding-space guard prevents (ADR-012, ADR-017). Then compare old and new on the golden set by slice with paired intervals and a three-valued gate (Chapter 18). Check index parameters, which are versioned with the model (Chapter 5), and re-measure recall under your real filters (Chapter 20). Roll back by keeping the old index until the new passes.

**Trade-offs.** Dual indexes cost storage during migration and make rollback safe. The component-5 design has no re-embed path for active versions yet (OI-054).

**Failure modes.** Mixed spaces in one index; a dimension change with a stale ANN index; metric normalisation differences between cosine and dot product (Chapter 2).

**Probes.** "How would you have caught this before release?" "What is your rollback?"

**Scoring focus.** Evaluation, operations.

**Draws on.** Chapters 2, 5, 18, 20; ADR-012, ADR-017; OI-054.

### SD-11 — A Prompt-Injection Incident

**Prompt.** A user uploaded a document that caused the assistant to reveal another user's information in a link. Respond and redesign.

**Clarify first.** What data left, through what channel, which controls existed, whether logs contain content, and the notification obligations.

**Model architecture.** Contain first (disable the feature or the source, rotate secrets, preserve content-free evidence). Then apply Chapter 22: the model is an untrusted component. Remove a leg of the lethal trifecta (private data, untrusted content, an exfiltration channel) or require human approval; block exfiltration channels deterministically, including URL and image rendering; frame and escape evidence so the structure holds even if the model is persuaded; enforce isolation in the database so the model could never have retrieved the other user's data; control and monitor corpus writes; keep logs content-free (Chapter 22, 19). In the exercise, a constructed 17-payload corpus and 3,000 fuzz cases were neutralised and 18 of 18 injected defects were detected **[X]**, without a real model, so model-based attack rates are unmeasured **[N]**.

**Trade-offs.** Stricter output policy blocks legitimate links; per-tenant isolation reduces blast radius at cost. Notification duties are a legal determination for counsel (Chapter 23).

**Failure modes.** Defence by prompt alone; a retrieval path that bypasses the filter; logs capturing the injected content and spreading it.

**Probes.** "What would have limited this to zero leaked bytes?" "How do you test your defences?"

**Scoring focus.** Security and isolation.

**Draws on.** Chapters 19, 22, 23.

### SD-12 — Right to Erasure and Retention

**Prompt.** A customer requests deletion of all their personal data, including from the assistant. Design the process.

**Clarify first.** Which jurisdictions, what stores hold derived data, backup and log retention, how long deletion may take, and who signs off.

**Model architecture.** Plan erasure across every derived store with stated residual windows: raw objects, extracted text, chunks, embeddings, caches, evaluation sets, logs, backups (Chapter 23). The data path should make deletion a cascade through composite keys and an outbox for external stores (Chapter 3, Chapter 14, ADR-014, ADR-015). Prove deletion with a test that queries every store, and record it in a content-free, tamper-evident audit log (Chapter 23). State the residual window for backups plainly.

**Trade-offs.** Immediate physical deletion conflicts with backup recovery; the documented compromise is a residual window with restore-time re-deletion **[E]**. Legal sufficiency is counsel's determination, and this handbook is not legal advice (Chapter 23).

**Failure modes.** Summaries or evaluation data retaining personal content; a vector left in an index; a cache returning the deleted answer.

**Probes.** "List every place the data lives." "How do you prove it is gone?"

**Scoring focus.** Security, operations.

**Draws on.** Chapters 3, 14, 23; ADR-014, ADR-015.

### SD-13 — A 2-Second p95 Budget

**Prompt.** The product requires p95 end-to-end under 2 seconds, with hybrid retrieval, reranking and a streamed answer.

**Clarify first.** Time to first token or full answer, region, concurrency, which components are optional, and acceptable degradation.

**Model architecture.** Allocate the budget per stage and measure each: query embedding, retrieval legs in parallel, fusion, rerank, context build, time to first token (Chapters 6, 12, 20). Reason about tail latency and fan-out: the slowest of N parallel calls governs (Chapter 20). Propagate deadlines, set timeouts from percentiles, retry at one layer with a budget, and degrade along an evaluated ladder that never drops a security control (Chapter 21). Reduce rerank depth, window long inputs, stream the answer, and cache the static prefix.

**Trade-offs.** A shallower rerank is faster and may lose the relevant chunk (depth 3 lost it, depth 4 or more kept it in my stand-in **[X]**, Chapter 12). The reference implementation has no request deadline yet (OI-058).

**Failure modes.** A retry storm turning a brown-out into a metastable outage (Chapter 21); a rerank timeout returning nothing instead of the fused order.

**Probes.** "What do you drop first under load?" "Where does the 2 seconds go?"

**Scoring focus.** Operations, trade-offs.

**Draws on.** Chapters 6, 12, 20, 21.

### SD-14 — Multi-Hop Questions Over Reports

**Prompt.** Analysts ask questions such as "which suppliers of the delayed project also supply the other flagged project?" Single-pass retrieval misses the second fact.

**Clarify first.** How common multi-hop questions are, the latency tolerance, the structure of the data, and the cost of a wrong answer.

**Model architecture.** Measure the failure class first. Add iterative retrieval where facts depend on each other, with a visited-set rule and a hop cap; consider a graph where relationships are stable (Chapter 11). Route simple questions around the loop (Chapter 30). If an agent chooses actions, treat its output as untrusted: harness-owned identity, allow-lists, budgets, loop control, approval and audit (Chapter 15). In my stand-in, a two-hop question missed its second document in one pass and succeeded iteratively, and fan-out raised recall@3 from 0.33 to 0.67 while promoting an irrelevant document **[X]**. Apply tenant filters on every hop.

**Trade-offs.** Iteration multiplies latency and cost (dependent decomposition dominates latency, Chapter 10 **[X]**); graph construction has index-time cost and ACL propagation problems. The literature warns many multi-hop benchmarks are solvable by shortcuts [S90].

**Failure modes.** Cyclic corpora; an injected instruction steering the next hop; permission leakage through graph edges (Chapter 11).

**Probes.** "Why not make it an agent?" "How do you stop it looping?"

**Scoring focus.** Retrieval depth, architecture fit.

**Draws on.** Chapters 10, 11, 15, 30.

### SD-15 — Regional Outage and Disaster Recovery

**Prompt.** The primary region is down for hours. What happens to the assistant, and what should have been prepared?

**Clarify first.** The recovery time and recovery point objectives per data class, regulatory residency, and whether degraded service is acceptable.

**Model architecture.** Set objectives per data class: raw objects are the source of truth, indexes are rebuildable, conversation data may have a different objective (Chapter 21). Make the data path at-least-once and idempotent so a rebuild is safe. PostgreSQL point-in-time recovery is whole-cluster, and everything must be rehearsed (Chapter 21). Degrade along an evaluated ladder (cached answers, lexical-only retrieval, read-only mode) that never drops a security control. Azure's baseline notes single-region and DR gaps that need explicit handling [S54].

**Trade-offs.** A warm standby costs continuous spend; a rebuild from raw objects is cheap and slow. Choose from the objectives, not from habit **[E]**. The reference implementation has no backups or high availability yet (OI-058).

**Failure modes.** A re-embed that takes days; an index restore that was never tested; a standby region with stale permissions.

**Probes.** "Which store do you restore first?" "What is your actual RTO, and how do you know?"

**Scoring focus.** Operations.

**Draws on.** Chapters 3, 7, 21; OI-058.

### SD-16 — Choosing the Vector Store

**Prompt.** The team must choose between Postgres with pgvector and a managed vector search service.

**Clarify first.** Corpus size, filter and tenancy patterns, hybrid needs, team skills, residency, and budget.

**Model architecture.** Decide from filter and tenancy fit, hybrid needs, scale, operations, cost and licence, not raw ANN speed (Chapter 5). The default in this reference implementation is Postgres with pgvector for transactional consistency with permissions and row-level security, with explicit triggers to move: scale beyond one instance's comfortable memory, need for a feature the engine lacks, or an operational burden the team cannot carry (ADR-001, Chapter 5). Other stores were not researched and are marked as such in the comparison **[N]**. Record the decision and its reversal conditions in an ADR (Chapter 31).

**Trade-offs.** pgvector gains one system and enforceable isolation, and loses some managed-service features; a managed store gains operations and scale, and may weaken permission enforcement or add egress.

**Failure modes.** Choosing on a benchmark that ignores filters; an index whose build exhausts container shared memory (OI-057, Chapter 20); no plan for index parameter changes.

**Probes.** "What would make you move off Postgres?" "Show me the decision record."

**Scoring focus.** Trade-offs and evolution.

**Draws on.** Chapters 5, 13, 20, 31; ADR-001.

### SD-17 — An Evaluation Program From Zero

**Prompt.** A team ships a RAG feature with no golden set and no metrics. Build the evaluation program.

**Clarify first.** Query sources, who can label, the risk profile, release cadence, and how permissions affect what a query may retrieve.

**Model architecture.** Build a versioned golden set judged by document and locator, with unanswerable, cross-tenant and hostile cases. Separate retrieval metrics (Recall@K, MRR, nDCG) from generation metrics (faithfulness, answer relevance, citation correctness). Validate any LLM judge with agreement statistics and swap tests. Compare versions with paired intervals and a three-valued gate (pass, fail, inconclusive). Report by slice. Run evaluation as an access-controlled system (Chapter 18). Add online monitoring: sample and judge production traffic, alert on an interval, and use SLOs with multiwindow burn-rate alerting (Chapter 19). Every change to chunking, embeddings, retrieval, reranking, prompts or models triggers regression evaluation (CLAUDE.md §12, Chapter 18).

**Trade-offs.** Human labels are expensive and trustworthy; judge models are cheap and biased. A small golden set gives wide intervals, which the sample-size simulations show **[X]** on synthetic data (Chapter 18). No real golden set or judge has been run in this repository (OI-056).

**Failure modes.** Optimising one metric; golden set leaking into prompts; evaluation data visible to people who should not see it.

**Probes.** "How many queries do you need to detect a 3-point change?" "How do you trust the judge?"

**Scoring focus.** Evaluation.

**Draws on.** Chapters 18, 19; OI-056.

## 32.7 Failure Modes of the Candidate **[E]**

| Pattern | What it looks like | Repair |
|---|---|---|
| Technology tour | Eight techniques, no requirement behind any | Start every addition with the requirement or measured failure it answers |
| Security as a footnote | "We will add auth" at minute 40 | State identity, enforcement point and untrusted-content rule at minute 10 |
| Invented numbers | Throughput figures with no source | Give formulas and label assumptions **[A]** |
| No evaluation | "We will test it with users" | Golden set, slices, gate |
| Single-metric thinking | Optimising latency or recall alone | Show the trade between quality, latency, cost and risk |
| No evolution | The design is final | State the first thing you would measure and what would change the decision |

## 32.8 Production Recommendations

1. Practise out loud, with a timer, and record the session **[E]**.
2. After each scenario, score yourself with §32.5 and write the weakest dimension at the top of the next session.
3. Keep a one-page reference of your own reversal conditions (Chapter 31); interviewers reward "I would reconsider if..." **[E]**.
4. Bring evidence, not claims: when you say "reranking helps", say what you would measure and against what baseline (Chapter 12).
5. Do not quote this handbook's executed numbers as industry benchmarks; they come from synthetic or constructed data on one host.
