# Chapter 33 — Advanced Interview Question Bank

> **Evidence legend.** **[S#]** = supported by a source cited in the chapter named by the question. **[X]** = executed in this repository by that chapter's exercise, on synthetic or constructed data unless stated. **[E]** = engineering reasoning. **[A]** = assumption. **[N]** = not researched. **Scope note:** the questions are original to this chapter (they complement, and do not repeat, the short questions at the end of each chapter) and the answers are syntheses of Chapters 1–31; no external interview material was researched (OI-075). Executed numbers are not benchmarks. Structure (identifier, chapter pointer, difficulty, answer, evidence tag, no duplicates, minimum counts) is checked by `docs/exercises/ch33_bank_lint.py`.

## 33.1 Learning Objectives

After this chapter you can:

1. Answer 100+ questions on RAG architecture at an intermediate-to-expert level, with the reasoning and the evidence, not just the conclusion.
2. Recognise which chapter holds the supporting evidence and the limits of that evidence.
3. Separate what this handbook measured on synthetic data from what it only reviewed or did not research.
4. Use the bank as a self-test: cover the answer, speak your own, then compare.

## 33.2 Problem Statement

Interview questions about RAG tend to reward vocabulary. A senior candidate is expected to give a mechanism, a trade-off, a failure mode and a way to verify. The bank is written so that each answer does that in a few sentences, and each answer says where the claim comes from.

## 33.3 Why It Matters in Production

The same questions come up in architecture reviews: "why this index, why this filter, how do you know it works, what happens when it fails". An answer that cannot be defended in an interview will not survive a review **[E]**.

## 33.4 How to Use the Bank

Questions are tagged with the chapter that carries the evidence and a difficulty: **foundational** (answerable by anyone who read the chapter), **intermediate** (needs a mechanism and a trade-off), **advanced** (needs combining chapters or reasoning about limits). Pair this chapter with the scenarios in Chapter 32. Each answer is compact; extend it aloud with the failure mode and the reversal condition.

## 33.5 Question Bank

### Foundations (Chapters 1–2)

**Q001 [Ch 1 · foundational]** When is long context a better answer than RAG?
**A.** When the corpus is small enough to fit, changes rarely, needs no per-user permissions, and the per-query cost is acceptable; Chapter 30's break-even arithmetic shows where retrieval starts to win on cost. RAG is much cheaper than long-context even when long-context is more accurate on average [S21], and models use long contexts unevenly [S19], so accuracy must be measured on your questions. **[S19, S21, X]**

**Q002 [Ch 1 · intermediate]** Why is fine-tuning not a substitute for retrieval of private, changing knowledge?
**A.** Fine-tuned knowledge cannot be permissioned per user, cited by passage, deleted on request or updated without retraining, which are properties of the RAG contract in Chapter 1 (fresh, private, citable, permissioned). Fine-tuning remains a complement for style and task behaviour. **[E]**

**Q003 [Ch 1 · advanced]** The model produced a fluent answer with a citation. Why is that not evidence that the answer is grounded?
**A.** A citation shows that the model named a source, not that the source supports the claim. Grounding must be verified [S23], for example by checking the cited passage was retrieved and by claim-support evaluation (Chapter 18). **[S23, E]**

**Q004 [Ch 2 · foundational]** Cosine, dot product and Euclidean distance: when do they give the same ranking?
**A.** On normalised vectors they coincide in ranking; on unnormalised vectors they diverge because dot product and Euclidean distance are affected by magnitude. Use the metric the model was trained for and record it with the embedding identity. **[X, E]**

**Q005 [Ch 2 · intermediate]** Why treat an embedding model as a schema version?
**A.** Vectors from different models are not comparable, and a model change alters every vector, so an index is valid only for the model, dimension and normalisation that produced it. Record the identity with each vector, guard against mixing spaces (the gateway's embedding-space guard, ADR-012), and keep the old index until the new one passes evaluation. **[E, X]**

**Q006 [Ch 2 · advanced]** Similarity is high but the answer is wrong. List non-geometric reasons.
**A.** Similarity is a proxy for relevance; relevance also includes authorization (the user may not see it), recency (the passage is superseded) and intent (the query asks something other than what the passage says). The chunk may also be right but lack its surrounding context (Chapter 4). **[E]**

### Ingestion and Chunking (Chapters 3–4)

**Q007 [Ch 3 · foundational]** What does idempotency at every stage buy in ingestion?
**A.** At-least-once delivery and retries cannot create duplicates or inconsistent state, so a failed or repeated job is safe to run again. In this project, versioning is idempotent and race-safe and chunk ids are content-derived so re-chunking converges (ADR-014, ADR-017). **[X, E]**

**Q008 [Ch 3 · intermediate]** Why must deletion be a first-class path in the ingestion design?
**A.** Derived copies (extracted text, chunks, embeddings, caches, evaluation sets) outlive the source otherwise, which breaks erasure and revocation. Deletion should cascade through composite keys and an outbox for external stores, and be verified across every store (Chapters 3, 14, 23). **[E]**

**Q009 [Ch 3 · advanced]** A malicious PDF arrives. What are the layers of defence in this reference design, and what is missing?
**A.** Parsing runs in a sandboxed child process with an empty environment, a timeout and an output cap, under a role that cannot read other tenants' data; text hygiene follows and extracted text is treated as untrusted. Missing: container-level isolation, and POSIX resource limits were not observed on the Windows host (OI-053). **[X, N]**

**Q010 [Ch 4 · foundational]** Name three chunking defects that silently cap retrieval quality.
**A.** Sentences cut in half, table headers detached from their rows, and context-free fragments that cannot be understood alone. Structure-aware chunking with heading paths and header-repeating table splits addresses them. **[E]**

**Q011 [Ch 4 · intermediate]** Why version the chunker like a schema?
**A.** Changing the chunker changes chunk boundaries and therefore every embedding, so the whole corpus must be re-embedded and re-evaluated. The reference chunker is named `structure-v1` for this reason (ADR-016). **[E, X]**

**Q012 [Ch 4 · advanced]** Someone proposes semantic chunking. What is your position?
**A.** Treat semantic chunking, LLM-generated chunk context and late chunking as experiments to be measured against deterministic structure-aware chunking on your content classes [S28, S34, S35]. Adopt where the golden set shows a gain per cost; default to the deterministic baseline because it is cheap, reproducible and testable. **[S28, S34, S35, E]**

### Embeddings and Vector Stores (Chapter 5)

**Q013 [Ch 5 · foundational]** What do HNSW and IVF trade away?
**A.** Both trade recall for speed and memory: HNSW through layered graphs, IVF through clustered lists, and quantization through smaller representations that need re-ranking [S39, S41, S46, S49]. The recall-versus-work dial was shown in this repository's demonstrations. **[S39, S41, S46, S49, X]**

**Q014 [Ch 5 · intermediate]** A fixed-candidate post-filter is placed after ANN search. What happens at 10% selectivity?
**A.** In the executed demonstration it returned about 4 of 10 results, because the filter discards most of a fixed candidate list [X, S1]. Pre-filtering, iterative scans or partitioning are the remedies, chosen by measured selectivity (Chapter 13). **[X, S1]**

**Q015 [Ch 5 · advanced]** What would make you move from Postgres with pgvector to a dedicated vector store?
**A.** Evidence that the default no longer meets requirements: scale beyond what one instance handles, a needed capability pgvector lacks, or an operational burden the team cannot carry, all stated as reversal conditions and tested on a real corpus. Other stores were not researched here, so any move needs its own evaluation of filter and tenancy fit. **[E, N]**

**Q016 [Ch 5 · advanced]** How do you decide a store's tenancy strategy?
**A.** Choose whether tenants share an index, a partition, or a shard from the tenant-size distribution, residency needs and the store's filter behaviour, because stores differ in whether they pre-filter, post-filter, iterate or fall back to brute force [S1, S7, S42, S45, S50]. Filtering and tenancy, not raw ANN speed, decide enterprise suitability. **[S1, S7, S42, S45, S50]**

### Retrieval Mechanics (Chapter 6)

**Q017 [Ch 6 · foundational]** What does reciprocal rank fusion do and why use ranks?
**A.** It merges ranked lists by summing 1/(k + rank) per document, so incompatible score scales do not matter. It is simple and robust (Chapter 9). **[X, S67]**

**Q018 [Ch 6 · intermediate]** Name two uncomfortable truths from the executed retrieval example.
**A.** Fusion can land between its inputs, and diversity re-ranking can displace relevant chunks; also, a generous K fills the context with weak candidates. They justify measuring rather than accepting defaults. **[X]**

**Q019 [Ch 6 · advanced]** Precision@K is 0.6 and Recall@K is 0.9. Is the retrieval good?
**A.** The two measure different things: recall says most relevant items are present, precision says 40% of what is shown is noise. Whether that is acceptable depends on downstream: a reranker can recover precision if recall is high, while noisy context may mislead generation. Read the metrics with MRR or nDCG, on positive and negative queries. **[E, X]**

### Architecture (Chapters 7–8)

**Q020 [Ch 7 · foundational]** What are the two paths of a RAG system and what do they share?
**A.** An offline ingestion path and an online query path, sharing an index, an embedding identity and preprocessing code. Divergence between them (different normalisation, different model) silently breaks retrieval. **[E]**

**Q021 [Ch 7 · intermediate]** Why is the online orchestrator deterministic?
**A.** It should pass an immutable identity to filtered retrieval, build a confined and delimited prompt from a constant template, call a pinned, bounded model, and validate citations deterministically, so that authorization and policy are code, not model behaviour. **[E, X]**

**Q022 [Ch 7 · advanced]** What can the application tier enforce on its own, and what can it not?
**A.** Tenant filtering, cache isolation, prompt confinement, citation validation and bounded model calls can be asserted in code and mutation-tested; the executed demonstration cannot show a real model resisting injection. A model resisting injection is not a guarantee to rely on (Chapter 22). **[X, E]**

**Q023 [Ch 8 · foundational]** Where must authorization filters be applied in retrieval?
**A.** Inside every retrieval leg, before limits, never after generation. A filter applied after the limit returns too few results or leaks. **[X, E]**

**Q024 [Ch 8 · intermediate]** How do you know your permission model and your retrieval filter agree?
**A.** Express the permission policy once, compile it into the filter, and prove equivalence by test over generated cases, as the executed demonstration did for group ACLs and attribute policies. Add database row-level security as a backstop under a restricted role. **[X, E]**

**Q025 [Ch 8 · advanced]** List platform caveats that turn into security properties.
**A.** Preview-only native ACL trimming, synchronization lag, shared scoring statistics across tenants, no user identities in platform logs, no native index restore, and manual cross-region promotion. Each needs a compensating control or explicit risk acceptance. **[E]**

**Q026 [Ch 8 · advanced]** How do you handle an on-behalf-of identity flow?
**A.** Validate tokens and propagate identity to the services that need the user, using on-behalf-of exchange where a downstream service must act as the user, and keep the identity immutable through the request. Do not let the model supply identity arguments (Chapter 15). **[S73, E]**

### Hybrid Search and Query Transformation (Chapters 9–11)

**Q027 [Ch 9 · foundational]** Why have a lexical leg at all?
**A.** Dense retrieval captures meaning and lexical retrieval captures exact terms such as identifiers and rare words; real systems need both. **[E, X]**

**Q028 [Ch 9 · intermediate]** What is a known limitation of Postgres built-in text ranking?
**A.** It lacks collection statistics such as IDF, so a rare and a common term can score identically (measured on synthetic data); the quality effect on real data is unmeasured. BM25 extensions exist with licensing implications. **[X, N]**

**Q029 [Ch 9 · advanced]** How would you choose between RRF and score fusion?
**A.** RRF is rank-based and robust to scale differences, with a constant near-optimal at 60 but not critical; score fusion keeps magnitude information but is sensitive to outliers and scale. Choose on a golden set, per query class. **[S67, E]**

**Q030 [Ch 10 · foundational]** What problem does query rewriting solve?
**A.** The gap between how users ask and how documents are written, for example pronoun follow-ups that retrieve nothing until rewritten. **[X]**

**Q031 [Ch 10 · intermediate]** Name two ways query transformation can hurt.
**A.** Always appending context contaminates topic switches, and expansion terms can wreck a query that worked until they are down-weighted; LLM expansion also helps weaker retrievers most and can hurt stronger ones [S84]. **[X, S84]**

**Q032 [Ch 10 · advanced]** Where must the original query stay, and why?
**A.** In the retrieval set, so a bad rewrite cannot make a working query worse; also never let model output set filters, bound and gate every LLM step, and evaluate per query class. **[E]**

**Q033 [Ch 11 · foundational]** What is multi-query retrieval?
**A.** Spreading one intent across several phrasings and fusing the results. In the stand-in demo fan-out raised recall@3 from 0.33 to 0.67. **[X]**

**Q034 [Ch 11 · intermediate]** What did fan-out get wrong in that demo?
**A.** It promoted an irrelevant document through consensus and let an off-topic variant displace a relevant one; reweighting the original did not fix that. **[X]**

**Q035 [Ch 11 · advanced]** How do you prevent an iterative retrieval loop from running away?
**A.** A visited-set rule with a hop cap as a backstop, budgets, and identity filters on every hop, with ACL-aware graphs; the cyclic-corpus demo terminated on the visited-set rule. **[X, E]**

### Reranking and Filtering (Chapters 12–13)

**Q036 [Ch 12 · foundational]** Can a reranker find a document the retriever missed?
**A.** No: it can only reorder its candidates. In the stand-in, depth 3 lost the relevant document and depth 4 or more kept it. **[X]**

**Q037 [Ch 12 · intermediate]** Why can a cross-encoder not precompute document scores?
**A.** It interacts query and document inside one model pass, so scores depend on the pair; late-interaction models precompute document token vectors and are claimed to be much cheaper per query at competitive quality [S95]. **[S95, E]**

**Q038 [Ch 12 · advanced]** A reranker score threshold is meant to detect "answer not present". Why is it unreliable?
**A.** Scores are not portable across scales and a scorer can rate a decoy higher than the true answer, so a threshold cannot signal absence by itself; calibrate on your data and combine with other signals. **[X, E]**

**Q039 [Ch 12 · advanced]** What must happen before sending candidates to an external reranker?
**A.** Authorization must precede the candidate cut and the rerank call, and data egress must be reviewed for a managed service. **[X, E]**

**Q040 [Ch 13 · foundational]** Why is a metadata filter also a security boundary?
**A.** Mandatory predicates such as tenant and ACL are enforced through the same mechanism as relevance filters; a bug or bypass is a leak. Untrusted filters must be allow-listed, type-checked, parameterised and AND-ed outside mandatory predicates. **[X, E]**

**Q041 [Ch 13 · intermediate]** What happens to an HNSW filtered search at 10%, 1% and 0.1% selectivity?
**A.** In the PG16 experiments a 10% filter returned 4.10 of 10 by default and 10.00 with iterative scan; 1% and 0.1% were rescued by the planner choosing a btree plan and an exact sort; a generic prepared-statement plan reversed the rescue (0.45 and 0.00 of 10). Synthetic data. **[X]**

**Q042 [Ch 13 · advanced]** How do you keep the rescue plan from silently disappearing?
**A.** Force custom plans, monitor returned counts and recall by selectivity band, and keep database-enforced isolation as the backstop. **[X, E]**

**Q043 [Ch 13 · advanced]** When is partitioning better than a filter on a shared index?
**A.** When tenants are large and queries are tenant-scoped: list partitioning pruned a tenant query to one partition and kept a 10% tenant at 10 of 10 without iteration; the cost is operational complexity for many small tenants. **[X, E]**

### Parent-Child and Agentic Retrieval (Chapters 14–15)

**Q044 [Ch 14 · foundational]** What does parent-child retrieval do?
**A.** It indexes small units for precise matching and returns larger units for reading. **[E]**

**Q045 [Ch 14 · intermediate]** Why must the child fetch exceed the number of parents wanted?
**A.** Children cluster into few parents: 10 children covered only 2.25 distinct parents in the clustered synthetic data. **[X]**

**Q046 [Ch 14 · advanced]** How can parent expansion leak data?
**A.** Naive expansion pulls in restricted siblings (6 versus 5 chunks in the demonstration), so ACLs must apply to the expanded set too. **[X]**

**Q047 [Ch 14 · advanced]** A budget policy skips a parent that is too big. What goes wrong?
**A.** It can discard the best evidence; truncating to a window around the matched child is safer. **[X]**

**Q048 [Ch 15 · foundational]** What is the main engineering point of agentic RAG?
**A.** The model's output is untrusted: identity, allow-lists, validation, approval, budgets, loop control, observation handling and audit belong to the harness, not the model. **[X, S110–S115]**

**Q049 [Ch 15 · intermediate]** When should you not use an agent?
**A.** When a fixed workflow meets the requirement: evidence advises the simplest workable design because agents cost more and add latency. Adopt autonomy last, behind controls. **[S110–S115, E]**

**Q050 [Ch 15 · advanced]** What did the layered-controls test show about defence in depth?
**A.** Removing one protective layer was masked by another, so tests of a single layer pass; only removing both was caught. Test each control with the others disabled. **[X]**

### Reference Implementation (Chapters 16–17)

**Q051 [Ch 16 · foundational]** Why a Postgres job queue instead of a broker?
**A.** It uses `SKIP LOCKED`, leases, retries and a dead state in the system already running, avoiding a new operational dependency; limits include no lease heartbeats (OI-052). **[X, E]**

**Q052 [Ch 16 · intermediate]** Why can the worker role not read arbitrary content?
**A.** `rag_worker` is limited to the job table and narrow, staged-only write paths with column grants, so a compromised worker has a small blast radius (ADR-015, ADR-016). **[X]**

**Q053 [Ch 16 · advanced]** What is the open weakness in the tenant-identity setting?
**A.** The application role could change its tenant identity via `set_config`; this is not exploitable in the current code but is a design question recorded in ADR-013's addendum and OI-069. **[X]**

**Q054 [Ch 17 · foundational]** Why return errors as RFC 9457 problem details that never echo input?
**A.** Echoing input or internals can leak data and credentials; a defect where credentials in exception text reached logs was found and fixed during the build. **[X]**

**Q055 [Ch 17 · intermediate]** What is the role of mutation testing in this project?
**A.** It checks the tests: injected defects must be killed. The embedding component had 27 of 28 mutants killed in the first run; the survivor exposed a weak test that was fixed. **[X]**

**Q056 [Ch 17 · advanced]** Why scope a pooled database transaction to a tenant?
**A.** With a pool, connection state could carry one tenant's identity into another request; setting identity inside each transaction and failing closed when unset prevents it (ADR-013). **[X, E]**

### Evaluation and Monitoring (Chapters 18–19)

**Q057 [Ch 18 · foundational]** Why separate retrieval from generation metrics?
**A.** A wrong answer may come from missing evidence or from misusing it; the fixes differ. **[E]**

**Q058 [Ch 18 · intermediate]** What must a golden set contain beyond normal queries?
**A.** Unanswerable, cross-tenant and hostile cases, judged by document and locator, versioned. **[E]**

**Q059 [Ch 18 · advanced]** How do you decide that version B is better than A?
**A.** Paired comparison with intervals and a three-valued gate (pass, fail, inconclusive), reported by slice; small sets give wide intervals, as the sample-size simulations show. **[X, E]**

**Q060 [Ch 18 · advanced]** How do you validate an LLM judge?
**A.** Agreement with human labels (kappa) and swap tests for position bias, then re-validate when the judge model changes. **[E]**

**Q061 [Ch 19 · foundational]** Why is availability monitoring not enough for RAG?
**A.** Quality can regress silently with no errors, so monitor quality by judging a sample and alert on an interval. **[E]**

**Q062 [Ch 19 · intermediate]** Why multiwindow, multi-burn-rate alerts?
**A.** They catch fast burns quickly and slow burns reliably while limiting false pages; understand also the incidents they deliberately ignore. **[X, E]**

**Q063 [Ch 19 · advanced]** What telemetry rules protect privacy?
**A.** Content off by default, allow-listed attributes, class-only errors and bounded labels, because telemetry is a data-collection system; OpenTelemetry's GenAI conventions are in Development, so use a mapping layer. **[X, E]**

### Performance and Reliability (Chapters 20–21)

**Q064 [Ch 20 · foundational]** What dominates the token bill?
**A.** Retrieved context and output; only the static prefix is cacheable. **[E]**

**Q065 [Ch 20 · intermediate]** How do you tune an ANN index responsibly?
**A.** By recall against exact results, and always check rows returned under real filters, where approximate indexes under-deliver unless iterative scans or another strategy are used. **[X, E]**

**Q066 [Ch 20 · advanced]** Why is p95 of a fan-out different from the p95 of one call?
**A.** The slowest of N parallel calls governs, so tail latency compounds with fan-out. **[E]**

**Q067 [Ch 20 · advanced]** Is quantizing vectors or reducing dimensions a free saving?
**A.** No: precision, dimension and index changes are retrieval changes that need evaluation. **[E]**

**Q068 [Ch 21 · foundational]** Where should you retry?
**A.** At one layer, with idempotent operations, jittered backoff and a budget; retries at several layers multiply load. **[X, E]**

**Q069 [Ch 21 · intermediate]** Why shed expired work?
**A.** Wasted work, not just retry volume, turns a brown-out into a metastable outage. **[X]**

**Q070 [Ch 21 · advanced]** What must never be dropped on a degradation ladder?
**A.** Security controls (authorization, isolation, output policy); degrade features and quality first. **[E]**

**Q071 [Ch 21 · advanced]** What is the limitation of PostgreSQL point-in-time recovery for a multi-tenant platform?
**A.** It is whole-cluster, so restoring one tenant's data needs another approach; everything must be rehearsed. **[E]**

### Security and Governance (Chapters 22–23)

**Q072 [Ch 22 · foundational]** Why treat the model as untrusted?
**A.** It sees untrusted text and private data and can be persuaded, so deterministic controls must surround it. **[X, E]**

**Q073 [Ch 22 · intermediate]** What is the lethal trifecta?
**A.** Private data, untrusted content and an exfiltration channel in one system; remove a leg or require human approval. **[E]**

**Q074 [Ch 22 · advanced]** Why block exfiltration channels deterministically?
**A.** Because the model may be persuaded to emit a link or image URL carrying data, so URL handling and rendering policy must not rely on the prompt. **[X, E]**

**Q075 [Ch 22 · advanced]** What did the security exercise not show?
**A.** It neutralised 17 constructed payloads and 3,000 fuzz cases without a real model, so model-based attack success rates are unmeasured. **[X, N]**

**Q076 [Ch 23 · foundational]** What does governance for RAG consist of?
**A.** An operating model, a register validated by policy as code, a risk mapping (the twelve NIST generative-AI risks), erasure planning, regulatory dates as data and an audit log. **[X, S164, S165]**

**Q077 [Ch 23 · intermediate]** Why a tamper-evident audit log, and what is its limit?
**A.** A hash chain makes silent edits detectable; the mutation survivor showed its limit, so anchor it externally. **[X]**

**Q078 [Ch 23 · advanced]** Can the handbook tell you that you comply with the EU AI Act?
**A.** No. It is not legal advice; the Act was read in part, ISO/IEC 42001 was not verified, and dates are time-sensitive. Counsel decides. **[N]**

### Use Cases (Chapters 24–29)

**Q079 [Ch 24 · foundational]** Synced or federated connectors?
**A.** Chosen per source: synced is fast and private to query but lags and duplicates permissions; federated is fresh but slower and limited by the source's search. **[E]**

**Q080 [Ch 24 · intermediate]** Why store group principals and resolve membership at query time?
**A.** So membership changes take effect without re-indexing every chunk. **[E]**

**Q081 [Ch 24 · advanced]** How do you bound permission staleness?
**A.** Set a maximum lag per source class, fail closed where exposure is costly, and run reconciliation as a fallback; the simulation showed an order-of-magnitude difference in exposure between designs (my parameters). **[X]**

**Q082 [Ch 25 · foundational]** Why disclose AI use first?
**A.** It is both an ethical and, in some jurisdictions, a regulatory expectation (Article 50 was read through a reproduction, so counsel should confirm). **[N]**

**Q083 [Ch 25 · intermediate]** Why is containment a misleading metric?
**A.** It overstated verified resolution by 21 points in the simulation; measure verified resolution. **[X]**

**Q084 [Ch 25 · advanced]** When may a bot make a commitment?
**A.** Only as a verbatim quotation of the cited, authoritative policy; high-risk intents always go to humans. **[E]**

**Q085 [Ch 26 · foundational]** How do you make fabricated citations structurally impossible?
**A.** Cite retrieved identifiers and render bibliographies from index metadata. **[E]**

**Q086 [Ch 26 · intermediate]** How do you verify a citation the model produced?
**A.** DOI lookup with metadata comparison, fuzzy matching with an ambiguity band, field-level error reporting and retraction checks. **[X, E]**

**Q087 [Ch 26 · advanced]** Why is an exact-match verifier a poor baseline?
**A.** It rejects correct citations on formatting alone; in the synthetic harness the full verifier detected all fabricated citations and flagged none of the harmless variants. **[X]**

**Q088 [Ch 27 · foundational]** Why chunk code by AST rather than lines?
**A.** On this repository's Python, line windows cut through functions in 73.7% of chunks against 3.0% for AST units. **[X]**

**Q089 [Ch 27 · intermediate]** Did AST chunking improve retrieval?
**A.** Not distinguishably: paired intervals spanned zero on 34 to 41 docstring-derived queries, a small single-repository lexical measurement. The retrieval case is open. **[X]**

**Q090 [Ch 27 · advanced]** How can a careless code-retrieval evaluation look perfect?
**A.** By leaking the answer into the query (for example docstring text); the leakage check demonstrated it. **[X]**

**Q091 [Ch 28 · foundational]** When use direct image embedding rather than extraction?
**A.** When layout or visual content carries meaning that text extraction loses; choose per content class by measurement. **[E]**

**Q092 [Ch 28 · intermediate]** What does a figure need to be retrievable and citable?
**A.** Linkage to its caption and referencing text, and a region locator; caption linking reached 99.0% versus 57.7% for a naive baseline on synthetic pages. **[X]**

**Q093 [Ch 28 · advanced]** What are the multimodal security risks?
**A.** Derived text from images and transcripts is untrusted and can carry injected instructions; transcripts can hallucinate speech; media parsing needs sandboxing. **[E]**

**Q094 [Ch 29 · foundational]** Why compute numbers in SQL rather than in the model?
**A.** The model can mis-calculate; the database is deterministic and auditable. **[E]**

**Q095 [Ch 29 · intermediate]** What does the restricted execution role consist of?
**A.** Column grants, forced row-level security, a read-only transaction, a timeout and a row cap; text filters are hygiene only (the guard stopped 21 of 21 attacks, a text pre-check passed 10). **[X]**

**Q096 [Ch 29 · advanced]** Why evaluate text-to-SQL on several datasets?
**A.** Different queries can return the same result on one dataset; execution accuracy agreed with the truth 100% only when run on two tenants. **[X]**

**Q097 [Ch 29 · advanced]** What did the unfinished mutation check mean?
**A.** The exercise's mutation check was not completed because the host disk filled (OI-071), so the guard's tests have a first passing run but no confirmation that they detect injected defects. **[X, N]**

### Patterns and Decisions (Chapters 30–31)

**Q098 [Ch 30 · foundational]** What principle governs pattern selection?
**A.** The smallest architecture that meets the requirements, adding pieces only with evidence [S213]. **[S213]**

**Q099 [Ch 30 · intermediate]** Which pattern suits which question type?
**A.** Long-context or routing for small corpora, iterative or graph retrieval for multi-hop, summary structures for global questions, text-to-SQL for aggregates. **[S213, E]**

**Q100 [Ch 30 · advanced]** What new problems do derived indexes bring?
**A.** Staleness and permission problems that a baseline index does not have. **[E]**

**Q101 [Ch 30 · advanced]** What did the pattern-selection exercise not show?
**A.** That the patterns perform. It showed the routing rules are consistent and the arithmetic is right; this repository has built none of them. **[X, N]**

**Q102 [Ch 31 · foundational]** Which decisions deserve an ADR?
**A.** Those affecting structure or key quality attributes, or hard to reverse [S215]. **[S215]**

**Q103 [Ch 31 · intermediate]** What did linting this repository's ADRs find?
**A.** No structural defects, and Accepted records that cite still-Proposed ones (ADR-002 and ADR-006), a human decision (OI-073). **[X]**

**Q104 [Ch 31 · advanced]** Why not fix that automatically?
**A.** Because the right response is a human decision about status informed by the evidence gaps, not a tool rewriting history. **[E]**

### Cross-Cutting (Advanced)

**Q105 [Ch 13 · advanced]** Your tenant-isolation design relies on a database filter. Name two ways it could still leak.
**A.** The identity setting the policy reads could be changed by the role (OI-069), and a cache or derived store (summaries, evaluation sets) could sit outside the policy. Test both. **[X, E]**

**Q106 [Ch 20 · advanced]** Quality fell after a cost cut. Which levers are the likely culprits and how do you diagnose?
**A.** Lower K, shallower rerank, quantization or smaller dimensions, cheaper model routing. Re-run the golden set by slice, compare paired intervals, and check returned counts under your filters. **[E]**

**Q107 [Ch 18 · advanced]** What stops evaluation itself from being a data leak?
**A.** Running it as a permission-aware, access-controlled part of the system with content-free reporting. **[E]**

**Q108 [Ch 21 · advanced]** Define recovery objectives for a RAG platform.
**A.** Per data class: raw objects are the source of truth, indexes are rebuildable, conversation data may differ; make the data path at-least-once and idempotent so rebuilds are safe, and rehearse. **[E]**

## 33.6 Failure Modes in Using the Bank

| Pattern | Risk | Repair |
|---|---|---|
| Memorising answers | Fails on follow-ups | Practise stating the mechanism and the failure mode |
| Quoting executed numbers as benchmarks | Overclaims | Say they come from synthetic data on one host |
| Ignoring the evidence tags | Cannot defend claims | Read the chapter behind the tag |
| Stopping at the answer | Misses trade-offs | Add the reversal condition |

## 33.7 Production Recommendations

1. Run the lint (`python -I docs/exercises/ch33_bank_lint.py`) after any edit **[E]**.
2. Add questions from real review findings; give each a chapter pointer and an evidence tag.
3. Retire or re-verify an answer when its chapter changes, especially version-sensitive content (Chapter 12 model options, Chapter 19 conventions, Chapter 23 regulation).
4. Do not present the bank as an official or industry-standard question set.

## 33.8 Knowledge Checkpoint / Exercises

1. Cover the answers for Q001–Q036, answer aloud, and score yourself foundational, intermediate and advanced separately.
2. Write ten new questions for Chapter 16, which has the thinnest executed evidence, and add them with the correct format.
3. Pick five answers and trace each evidence tag to the sentence in the cited chapter that supports it; report any that do not.
4. Convert Q105–Q108 into full scenarios in the Chapter 32 structure.

## 33.9 Summary

The bank holds 108 questions across Chapters 1–31, each with a compact model answer and an evidence tag, plus a lint that checks structure. It supports practice and review. It does not replace the chapters, it was not validated against real interviews, and its answers inherit the limits of the evidence in the chapters they cite (OI-075).

## References

- Chapters 1–31 of this handbook, cited per question; sources [S19], [S21], [S23], [S28], [S34], [S35], [S39], [S41], [S46], [S49], [S1], [S7], [S42], [S45], [S50], [S67], [S73], [S84], [S95], [S164], [S165], [S110]–[S115], [S213], [S215] as registered in `project-management/RESEARCH-REGISTER.md`.
- ADR-012 to ADR-017; OI-052, OI-053, OI-069, OI-071, OI-073, OI-075 in `project-management/OPEN-ISSUES.md`.
- Validator: `docs/exercises/ch33_bank_lint.py`.
