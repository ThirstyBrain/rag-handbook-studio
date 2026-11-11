# RAG Flashcards

> GENERATED FILE from `docs/chapters/33-advanced-interview-question-bank.md` (108 cards). Cover the answer, say yours aloud, then expand. Evidence tags are defined in the [question bank](../08-Interview-Question-Bank.md). Rebuild: `python -I scripts/build-interview-pack.py`.

<details><summary><b>Q001</b> · Ch 1 · foundational: When is long context a better answer than RAG?</summary>

When the corpus is small enough to fit, changes rarely, needs no per-user permissions, and the per-query cost is acceptable; Chapter 30's break-even arithmetic shows where retrieval starts to win on cost. RAG is much cheaper than long-context even when long-context is more accurate on average [S21], and models use long contexts unevenly [S19], so accuracy must be measured on your questions. **[S19, S21, X]**

</details>

<details><summary><b>Q002</b> · Ch 1 · intermediate: Why is fine-tuning not a substitute for retrieval of private, changing knowledge?</summary>

Fine-tuned knowledge cannot be permissioned per user, cited by passage, deleted on request or updated without retraining, which are properties of the RAG contract in Chapter 1 (fresh, private, citable, permissioned). Fine-tuning remains a complement for style and task behaviour. **[E]**

</details>

<details><summary><b>Q003</b> · Ch 1 · advanced: The model produced a fluent answer with a citation. Why is that not evidence that the answer is grounded?</summary>

A citation shows that the model named a source, not that the source supports the claim. Grounding must be verified [S23], for example by checking the cited passage was retrieved and by claim-support evaluation (Chapter 18). **[S23, E]**

</details>

<details><summary><b>Q004</b> · Ch 2 · foundational: Cosine, dot product and Euclidean distance: when do they give the same ranking?</summary>

On normalised vectors they coincide in ranking; on unnormalised vectors they diverge because dot product and Euclidean distance are affected by magnitude. Use the metric the model was trained for and record it with the embedding identity. **[X, E]**

</details>

<details><summary><b>Q005</b> · Ch 2 · intermediate: Why treat an embedding model as a schema version?</summary>

Vectors from different models are not comparable, and a model change alters every vector, so an index is valid only for the model, dimension and normalisation that produced it. Record the identity with each vector, guard against mixing spaces (the gateway's embedding-space guard, ADR-012), and keep the old index until the new one passes evaluation. **[E, X]**

</details>

<details><summary><b>Q006</b> · Ch 2 · advanced: Similarity is high but the answer is wrong. List non-geometric reasons.</summary>

Similarity is a proxy for relevance; relevance also includes authorization (the user may not see it), recency (the passage is superseded) and intent (the query asks something other than what the passage says). The chunk may also be right but lack its surrounding context (Chapter 4). **[E]**

</details>

<details><summary><b>Q007</b> · Ch 3 · foundational: What does idempotency at every stage buy in ingestion?</summary>

At-least-once delivery and retries cannot create duplicates or inconsistent state, so a failed or repeated job is safe to run again. In this project, versioning is idempotent and race-safe and chunk ids are content-derived so re-chunking converges (ADR-014, ADR-017). **[X, E]**

</details>

<details><summary><b>Q008</b> · Ch 3 · intermediate: Why must deletion be a first-class path in the ingestion design?</summary>

Derived copies (extracted text, chunks, embeddings, caches, evaluation sets) outlive the source otherwise, which breaks erasure and revocation. Deletion should cascade through composite keys and an outbox for external stores, and be verified across every store (Chapters 3, 14, 23). **[E]**

</details>

<details><summary><b>Q009</b> · Ch 3 · advanced: A malicious PDF arrives. What are the layers of defence in this reference design, and what is missing?</summary>

Parsing runs in a sandboxed child process with an empty environment, a timeout and an output cap, under a role that cannot read other tenants' data; text hygiene follows and extracted text is treated as untrusted. Missing: container-level isolation, and POSIX resource limits were not observed on the Windows host (OI-053). **[X, N]**

</details>

<details><summary><b>Q010</b> · Ch 4 · foundational: Name three chunking defects that silently cap retrieval quality.</summary>

Sentences cut in half, table headers detached from their rows, and context-free fragments that cannot be understood alone. Structure-aware chunking with heading paths and header-repeating table splits addresses them. **[E]**

</details>

<details><summary><b>Q011</b> · Ch 4 · intermediate: Why version the chunker like a schema?</summary>

Changing the chunker changes chunk boundaries and therefore every embedding, so the whole corpus must be re-embedded and re-evaluated. The reference chunker is named `structure-v1` for this reason (ADR-016). **[E, X]**

</details>

<details><summary><b>Q012</b> · Ch 4 · advanced: Someone proposes semantic chunking. What is your position?</summary>

Treat semantic chunking, LLM-generated chunk context and late chunking as experiments to be measured against deterministic structure-aware chunking on your content classes [S28, S34, S35]. Adopt where the golden set shows a gain per cost; default to the deterministic baseline because it is cheap, reproducible and testable. **[S28, S34, S35, E]**

</details>

<details><summary><b>Q013</b> · Ch 5 · foundational: What do HNSW and IVF trade away?</summary>

Both trade recall for speed and memory: HNSW through layered graphs, IVF through clustered lists, and quantization through smaller representations that need re-ranking [S39, S41, S46, S49]. The recall-versus-work dial was shown in this repository's demonstrations. **[S39, S41, S46, S49, X]**

</details>

<details><summary><b>Q014</b> · Ch 5 · intermediate: A fixed-candidate post-filter is placed after ANN search. What happens at 10% selectivity?</summary>

In the executed demonstration it returned about 4 of 10 results, because the filter discards most of a fixed candidate list [X, S1]. Pre-filtering, iterative scans or partitioning are the remedies, chosen by measured selectivity (Chapter 13). **[X, S1]**

</details>

<details><summary><b>Q015</b> · Ch 5 · advanced: What would make you move from Postgres with pgvector to a dedicated vector store?</summary>

Evidence that the default no longer meets requirements: scale beyond what one instance handles, a needed capability pgvector lacks, or an operational burden the team cannot carry, all stated as reversal conditions and tested on a real corpus. Other stores were not researched here, so any move needs its own evaluation of filter and tenancy fit. **[E, N]**

</details>

<details><summary><b>Q016</b> · Ch 5 · advanced: How do you decide a store's tenancy strategy?</summary>

Choose whether tenants share an index, a partition, or a shard from the tenant-size distribution, residency needs and the store's filter behaviour, because stores differ in whether they pre-filter, post-filter, iterate or fall back to brute force [S1, S7, S42, S45, S50]. Filtering and tenancy, not raw ANN speed, decide enterprise suitability. **[S1, S7, S42, S45, S50]**

</details>

<details><summary><b>Q017</b> · Ch 6 · foundational: What does reciprocal rank fusion do and why use ranks?</summary>

It merges ranked lists by summing 1/(k + rank) per document, so incompatible score scales do not matter. It is simple and robust (Chapter 9). **[X, S67]**

</details>

<details><summary><b>Q018</b> · Ch 6 · intermediate: Name two uncomfortable truths from the executed retrieval example.</summary>

Fusion can land between its inputs, and diversity re-ranking can displace relevant chunks; also, a generous K fills the context with weak candidates. They justify measuring rather than accepting defaults. **[X]**

</details>

<details><summary><b>Q019</b> · Ch 6 · advanced: Precision@K is 0.6 and Recall@K is 0.9. Is the retrieval good?</summary>

The two measure different things: recall says most relevant items are present, precision says 40% of what is shown is noise. Whether that is acceptable depends on downstream: a reranker can recover precision if recall is high, while noisy context may mislead generation. Read the metrics with MRR or nDCG, on positive and negative queries. **[E, X]**

</details>

<details><summary><b>Q020</b> · Ch 7 · foundational: What are the two paths of a RAG system and what do they share?</summary>

An offline ingestion path and an online query path, sharing an index, an embedding identity and preprocessing code. Divergence between them (different normalisation, different model) silently breaks retrieval. **[E]**

</details>

<details><summary><b>Q021</b> · Ch 7 · intermediate: Why is the online orchestrator deterministic?</summary>

It should pass an immutable identity to filtered retrieval, build a confined and delimited prompt from a constant template, call a pinned, bounded model, and validate citations deterministically, so that authorization and policy are code, not model behaviour. **[E, X]**

</details>

<details><summary><b>Q022</b> · Ch 7 · advanced: What can the application tier enforce on its own, and what can it not?</summary>

Tenant filtering, cache isolation, prompt confinement, citation validation and bounded model calls can be asserted in code and mutation-tested; the executed demonstration cannot show a real model resisting injection. A model resisting injection is not a guarantee to rely on (Chapter 22). **[X, E]**

</details>

<details><summary><b>Q023</b> · Ch 8 · foundational: Where must authorization filters be applied in retrieval?</summary>

Inside every retrieval leg, before limits, never after generation. A filter applied after the limit returns too few results or leaks. **[X, E]**

</details>

<details><summary><b>Q024</b> · Ch 8 · intermediate: How do you know your permission model and your retrieval filter agree?</summary>

Express the permission policy once, compile it into the filter, and prove equivalence by test over generated cases, as the executed demonstration did for group ACLs and attribute policies. Add database row-level security as a backstop under a restricted role. **[X, E]**

</details>

<details><summary><b>Q025</b> · Ch 8 · advanced: List platform caveats that turn into security properties.</summary>

Preview-only native ACL trimming, synchronization lag, shared scoring statistics across tenants, no user identities in platform logs, no native index restore, and manual cross-region promotion. Each needs a compensating control or explicit risk acceptance. **[E]**

</details>

<details><summary><b>Q026</b> · Ch 8 · advanced: How do you handle an on-behalf-of identity flow?</summary>

Validate tokens and propagate identity to the services that need the user, using on-behalf-of exchange where a downstream service must act as the user, and keep the identity immutable through the request. Do not let the model supply identity arguments (Chapter 15). **[S73, E]**

</details>

<details><summary><b>Q027</b> · Ch 9 · foundational: Why have a lexical leg at all?</summary>

Dense retrieval captures meaning and lexical retrieval captures exact terms such as identifiers and rare words; real systems need both. **[E, X]**

</details>

<details><summary><b>Q028</b> · Ch 9 · intermediate: What is a known limitation of Postgres built-in text ranking?</summary>

It lacks collection statistics such as IDF, so a rare and a common term can score identically (measured on synthetic data); the quality effect on real data is unmeasured. BM25 extensions exist with licensing implications. **[X, N]**

</details>

<details><summary><b>Q029</b> · Ch 9 · advanced: How would you choose between RRF and score fusion?</summary>

RRF is rank-based and robust to scale differences, with a constant near-optimal at 60 but not critical; score fusion keeps magnitude information but is sensitive to outliers and scale. Choose on a golden set, per query class. **[S67, E]**

</details>

<details><summary><b>Q030</b> · Ch 10 · foundational: What problem does query rewriting solve?</summary>

The gap between how users ask and how documents are written, for example pronoun follow-ups that retrieve nothing until rewritten. **[X]**

</details>

<details><summary><b>Q031</b> · Ch 10 · intermediate: Name two ways query transformation can hurt.</summary>

Always appending context contaminates topic switches, and expansion terms can wreck a query that worked until they are down-weighted; LLM expansion also helps weaker retrievers most and can hurt stronger ones [S84]. **[X, S84]**

</details>

<details><summary><b>Q032</b> · Ch 10 · advanced: Where must the original query stay, and why?</summary>

In the retrieval set, so a bad rewrite cannot make a working query worse; also never let model output set filters, bound and gate every LLM step, and evaluate per query class. **[E]**

</details>

<details><summary><b>Q033</b> · Ch 11 · foundational: What is multi-query retrieval?</summary>

Spreading one intent across several phrasings and fusing the results. In the stand-in demo fan-out raised recall@3 from 0.33 to 0.67. **[X]**

</details>

<details><summary><b>Q034</b> · Ch 11 · intermediate: What did fan-out get wrong in that demo?</summary>

It promoted an irrelevant document through consensus and let an off-topic variant displace a relevant one; reweighting the original did not fix that. **[X]**

</details>

<details><summary><b>Q035</b> · Ch 11 · advanced: How do you prevent an iterative retrieval loop from running away?</summary>

A visited-set rule with a hop cap as a backstop, budgets, and identity filters on every hop, with ACL-aware graphs; the cyclic-corpus demo terminated on the visited-set rule. **[X, E]**

</details>

<details><summary><b>Q036</b> · Ch 12 · foundational: Can a reranker find a document the retriever missed?</summary>

No: it can only reorder its candidates. In the stand-in, depth 3 lost the relevant document and depth 4 or more kept it. **[X]**

</details>

<details><summary><b>Q037</b> · Ch 12 · intermediate: Why can a cross-encoder not precompute document scores?</summary>

It interacts query and document inside one model pass, so scores depend on the pair; late-interaction models precompute document token vectors and are claimed to be much cheaper per query at competitive quality [S95]. **[S95, E]**

</details>

<details><summary><b>Q038</b> · Ch 12 · advanced: A reranker score threshold is meant to detect "answer not present". Why is it unreliable?</summary>

Scores are not portable across scales and a scorer can rate a decoy higher than the true answer, so a threshold cannot signal absence by itself; calibrate on your data and combine with other signals. **[X, E]**

</details>

<details><summary><b>Q039</b> · Ch 12 · advanced: What must happen before sending candidates to an external reranker?</summary>

Authorization must precede the candidate cut and the rerank call, and data egress must be reviewed for a managed service. **[X, E]**

</details>

<details><summary><b>Q040</b> · Ch 13 · foundational: Why is a metadata filter also a security boundary?</summary>

Mandatory predicates such as tenant and ACL are enforced through the same mechanism as relevance filters; a bug or bypass is a leak. Untrusted filters must be allow-listed, type-checked, parameterised and AND-ed outside mandatory predicates. **[X, E]**

</details>

<details><summary><b>Q041</b> · Ch 13 · intermediate: What happens to an HNSW filtered search at 10%, 1% and 0.1% selectivity?</summary>

In the PG16 experiments a 10% filter returned 4.10 of 10 by default and 10.00 with iterative scan; 1% and 0.1% were rescued by the planner choosing a btree plan and an exact sort; a generic prepared-statement plan reversed the rescue (0.45 and 0.00 of 10). Synthetic data. **[X]**

</details>

<details><summary><b>Q042</b> · Ch 13 · advanced: How do you keep the rescue plan from silently disappearing?</summary>

Force custom plans, monitor returned counts and recall by selectivity band, and keep database-enforced isolation as the backstop. **[X, E]**

</details>

<details><summary><b>Q043</b> · Ch 13 · advanced: When is partitioning better than a filter on a shared index?</summary>

When tenants are large and queries are tenant-scoped: list partitioning pruned a tenant query to one partition and kept a 10% tenant at 10 of 10 without iteration; the cost is operational complexity for many small tenants. **[X, E]**

</details>

<details><summary><b>Q044</b> · Ch 14 · foundational: What does parent-child retrieval do?</summary>

It indexes small units for precise matching and returns larger units for reading. **[E]**

</details>

<details><summary><b>Q045</b> · Ch 14 · intermediate: Why must the child fetch exceed the number of parents wanted?</summary>

Children cluster into few parents: 10 children covered only 2.25 distinct parents in the clustered synthetic data. **[X]**

</details>

<details><summary><b>Q046</b> · Ch 14 · advanced: How can parent expansion leak data?</summary>

Naive expansion pulls in restricted siblings (6 versus 5 chunks in the demonstration), so ACLs must apply to the expanded set too. **[X]**

</details>

<details><summary><b>Q047</b> · Ch 14 · advanced: A budget policy skips a parent that is too big. What goes wrong?</summary>

It can discard the best evidence; truncating to a window around the matched child is safer. **[X]**

</details>

<details><summary><b>Q048</b> · Ch 15 · foundational: What is the main engineering point of agentic RAG?</summary>

The model's output is untrusted: identity, allow-lists, validation, approval, budgets, loop control, observation handling and audit belong to the harness, not the model. **[X, S110–S115]**

</details>

<details><summary><b>Q049</b> · Ch 15 · intermediate: When should you not use an agent?</summary>

When a fixed workflow meets the requirement: evidence advises the simplest workable design because agents cost more and add latency. Adopt autonomy last, behind controls. **[S110–S115, E]**

</details>

<details><summary><b>Q050</b> · Ch 15 · advanced: What did the layered-controls test show about defence in depth?</summary>

Removing one protective layer was masked by another, so tests of a single layer pass; only removing both was caught. Test each control with the others disabled. **[X]**

</details>

<details><summary><b>Q051</b> · Ch 16 · foundational: Why a Postgres job queue instead of a broker?</summary>

It uses `SKIP LOCKED`, leases, retries and a dead state in the system already running, avoiding a new operational dependency; limits include no lease heartbeats (OI-052). **[X, E]**

</details>

<details><summary><b>Q052</b> · Ch 16 · intermediate: Why can the worker role not read arbitrary content?</summary>

`rag_worker` is limited to the job table and narrow, staged-only write paths with column grants, so a compromised worker has a small blast radius (ADR-015, ADR-016). **[X]**

</details>

<details><summary><b>Q053</b> · Ch 16 · advanced: What is the open weakness in the tenant-identity setting?</summary>

The application role could change its tenant identity via `set_config`; this is not exploitable in the current code but is a design question recorded in ADR-013's addendum and OI-069. **[X]**

</details>

<details><summary><b>Q054</b> · Ch 17 · foundational: Why return errors as RFC 9457 problem details that never echo input?</summary>

Echoing input or internals can leak data and credentials; a defect where credentials in exception text reached logs was found and fixed during the build. **[X]**

</details>

<details><summary><b>Q055</b> · Ch 17 · intermediate: What is the role of mutation testing in this project?</summary>

It checks the tests: injected defects must be killed. The embedding component had 27 of 28 mutants killed in the first run; the survivor exposed a weak test that was fixed. **[X]**

</details>

<details><summary><b>Q056</b> · Ch 17 · advanced: Why scope a pooled database transaction to a tenant?</summary>

With a pool, connection state could carry one tenant's identity into another request; setting identity inside each transaction and failing closed when unset prevents it (ADR-013). **[X, E]**

</details>

<details><summary><b>Q057</b> · Ch 18 · foundational: Why separate retrieval from generation metrics?</summary>

A wrong answer may come from missing evidence or from misusing it; the fixes differ. **[E]**

</details>

<details><summary><b>Q058</b> · Ch 18 · intermediate: What must a golden set contain beyond normal queries?</summary>

Unanswerable, cross-tenant and hostile cases, judged by document and locator, versioned. **[E]**

</details>

<details><summary><b>Q059</b> · Ch 18 · advanced: How do you decide that version B is better than A?</summary>

Paired comparison with intervals and a three-valued gate (pass, fail, inconclusive), reported by slice; small sets give wide intervals, as the sample-size simulations show. **[X, E]**

</details>

<details><summary><b>Q060</b> · Ch 18 · advanced: How do you validate an LLM judge?</summary>

Agreement with human labels (kappa) and swap tests for position bias, then re-validate when the judge model changes. **[E]**

</details>

<details><summary><b>Q061</b> · Ch 19 · foundational: Why is availability monitoring not enough for RAG?</summary>

Quality can regress silently with no errors, so monitor quality by judging a sample and alert on an interval. **[E]**

</details>

<details><summary><b>Q062</b> · Ch 19 · intermediate: Why multiwindow, multi-burn-rate alerts?</summary>

They catch fast burns quickly and slow burns reliably while limiting false pages; understand also the incidents they deliberately ignore. **[X, E]**

</details>

<details><summary><b>Q063</b> · Ch 19 · advanced: What telemetry rules protect privacy?</summary>

Content off by default, allow-listed attributes, class-only errors and bounded labels, because telemetry is a data-collection system; OpenTelemetry's GenAI conventions are in Development, so use a mapping layer. **[X, E]**

</details>

<details><summary><b>Q064</b> · Ch 20 · foundational: What dominates the token bill?</summary>

Retrieved context and output; only the static prefix is cacheable. **[E]**

</details>

<details><summary><b>Q065</b> · Ch 20 · intermediate: How do you tune an ANN index responsibly?</summary>

By recall against exact results, and always check rows returned under real filters, where approximate indexes under-deliver unless iterative scans or another strategy are used. **[X, E]**

</details>

<details><summary><b>Q066</b> · Ch 20 · advanced: Why is p95 of a fan-out different from the p95 of one call?</summary>

The slowest of N parallel calls governs, so tail latency compounds with fan-out. **[E]**

</details>

<details><summary><b>Q067</b> · Ch 20 · advanced: Is quantizing vectors or reducing dimensions a free saving?</summary>

No: precision, dimension and index changes are retrieval changes that need evaluation. **[E]**

</details>

<details><summary><b>Q068</b> · Ch 21 · foundational: Where should you retry?</summary>

At one layer, with idempotent operations, jittered backoff and a budget; retries at several layers multiply load. **[X, E]**

</details>

<details><summary><b>Q069</b> · Ch 21 · intermediate: Why shed expired work?</summary>

Wasted work, not just retry volume, turns a brown-out into a metastable outage. **[X]**

</details>

<details><summary><b>Q070</b> · Ch 21 · advanced: What must never be dropped on a degradation ladder?</summary>

Security controls (authorization, isolation, output policy); degrade features and quality first. **[E]**

</details>

<details><summary><b>Q071</b> · Ch 21 · advanced: What is the limitation of PostgreSQL point-in-time recovery for a multi-tenant platform?</summary>

It is whole-cluster, so restoring one tenant's data needs another approach; everything must be rehearsed. **[E]**

</details>

<details><summary><b>Q072</b> · Ch 22 · foundational: Why treat the model as untrusted?</summary>

It sees untrusted text and private data and can be persuaded, so deterministic controls must surround it. **[X, E]**

</details>

<details><summary><b>Q073</b> · Ch 22 · intermediate: What is the lethal trifecta?</summary>

Private data, untrusted content and an exfiltration channel in one system; remove a leg or require human approval. **[E]**

</details>

<details><summary><b>Q074</b> · Ch 22 · advanced: Why block exfiltration channels deterministically?</summary>

Because the model may be persuaded to emit a link or image URL carrying data, so URL handling and rendering policy must not rely on the prompt. **[X, E]**

</details>

<details><summary><b>Q075</b> · Ch 22 · advanced: What did the security exercise not show?</summary>

It neutralised 17 constructed payloads and 3,000 fuzz cases without a real model, so model-based attack success rates are unmeasured. **[X, N]**

</details>

<details><summary><b>Q076</b> · Ch 23 · foundational: What does governance for RAG consist of?</summary>

An operating model, a register validated by policy as code, a risk mapping (the twelve NIST generative-AI risks), erasure planning, regulatory dates as data and an audit log. **[X, S164, S165]**

</details>

<details><summary><b>Q077</b> · Ch 23 · intermediate: Why a tamper-evident audit log, and what is its limit?</summary>

A hash chain makes silent edits detectable; the mutation survivor showed its limit, so anchor it externally. **[X]**

</details>

<details><summary><b>Q078</b> · Ch 23 · advanced: Can the handbook tell you that you comply with the EU AI Act?</summary>

No. It is not legal advice; the Act was read in part, ISO/IEC 42001 was not verified, and dates are time-sensitive. Counsel decides. **[N]**

</details>

<details><summary><b>Q079</b> · Ch 24 · foundational: Synced or federated connectors?</summary>

Chosen per source: synced is fast and private to query but lags and duplicates permissions; federated is fresh but slower and limited by the source's search. **[E]**

</details>

<details><summary><b>Q080</b> · Ch 24 · intermediate: Why store group principals and resolve membership at query time?</summary>

So membership changes take effect without re-indexing every chunk. **[E]**

</details>

<details><summary><b>Q081</b> · Ch 24 · advanced: How do you bound permission staleness?</summary>

Set a maximum lag per source class, fail closed where exposure is costly, and run reconciliation as a fallback; the simulation showed an order-of-magnitude difference in exposure between designs (my parameters). **[X]**

</details>

<details><summary><b>Q082</b> · Ch 25 · foundational: Why disclose AI use first?</summary>

It is both an ethical and, in some jurisdictions, a regulatory expectation (Article 50 was read through a reproduction, so counsel should confirm). **[N]**

</details>

<details><summary><b>Q083</b> · Ch 25 · intermediate: Why is containment a misleading metric?</summary>

It overstated verified resolution by 21 points in the simulation; measure verified resolution. **[X]**

</details>

<details><summary><b>Q084</b> · Ch 25 · advanced: When may a bot make a commitment?</summary>

Only as a verbatim quotation of the cited, authoritative policy; high-risk intents always go to humans. **[E]**

</details>

<details><summary><b>Q085</b> · Ch 26 · foundational: How do you make fabricated citations structurally impossible?</summary>

Cite retrieved identifiers and render bibliographies from index metadata. **[E]**

</details>

<details><summary><b>Q086</b> · Ch 26 · intermediate: How do you verify a citation the model produced?</summary>

DOI lookup with metadata comparison, fuzzy matching with an ambiguity band, field-level error reporting and retraction checks. **[X, E]**

</details>

<details><summary><b>Q087</b> · Ch 26 · advanced: Why is an exact-match verifier a poor baseline?</summary>

It rejects correct citations on formatting alone; in the synthetic harness the full verifier detected all fabricated citations and flagged none of the harmless variants. **[X]**

</details>

<details><summary><b>Q088</b> · Ch 27 · foundational: Why chunk code by AST rather than lines?</summary>

On this repository's Python, line windows cut through functions in 73.7% of chunks against 3.0% for AST units. **[X]**

</details>

<details><summary><b>Q089</b> · Ch 27 · intermediate: Did AST chunking improve retrieval?</summary>

Not distinguishably: paired intervals spanned zero on 34 to 41 docstring-derived queries, a small single-repository lexical measurement. The retrieval case is open. **[X]**

</details>

<details><summary><b>Q090</b> · Ch 27 · advanced: How can a careless code-retrieval evaluation look perfect?</summary>

By leaking the answer into the query (for example docstring text); the leakage check demonstrated it. **[X]**

</details>

<details><summary><b>Q091</b> · Ch 28 · foundational: When use direct image embedding rather than extraction?</summary>

When layout or visual content carries meaning that text extraction loses; choose per content class by measurement. **[E]**

</details>

<details><summary><b>Q092</b> · Ch 28 · intermediate: What does a figure need to be retrievable and citable?</summary>

Linkage to its caption and referencing text, and a region locator; caption linking reached 99.0% versus 57.7% for a naive baseline on synthetic pages. **[X]**

</details>

<details><summary><b>Q093</b> · Ch 28 · advanced: What are the multimodal security risks?</summary>

Derived text from images and transcripts is untrusted and can carry injected instructions; transcripts can hallucinate speech; media parsing needs sandboxing. **[E]**

</details>

<details><summary><b>Q094</b> · Ch 29 · foundational: Why compute numbers in SQL rather than in the model?</summary>

The model can mis-calculate; the database is deterministic and auditable. **[E]**

</details>

<details><summary><b>Q095</b> · Ch 29 · intermediate: What does the restricted execution role consist of?</summary>

Column grants, forced row-level security, a read-only transaction, a timeout and a row cap; text filters are hygiene only (the guard stopped 21 of 21 attacks, a text pre-check passed 10). **[X]**

</details>

<details><summary><b>Q096</b> · Ch 29 · advanced: Why evaluate text-to-SQL on several datasets?</summary>

Different queries can return the same result on one dataset; execution accuracy agreed with the truth 100% only when run on two tenants. **[X]**

</details>

<details><summary><b>Q097</b> · Ch 29 · advanced: What did the unfinished mutation check mean?</summary>

The exercise's mutation check was not completed because the host disk filled (OI-071), so the guard's tests have a first passing run but no confirmation that they detect injected defects. **[X, N]**

</details>

<details><summary><b>Q098</b> · Ch 30 · foundational: What principle governs pattern selection?</summary>

The smallest architecture that meets the requirements, adding pieces only with evidence [S213]. **[S213]**

</details>

<details><summary><b>Q099</b> · Ch 30 · intermediate: Which pattern suits which question type?</summary>

Long-context or routing for small corpora, iterative or graph retrieval for multi-hop, summary structures for global questions, text-to-SQL for aggregates. **[S213, E]**

</details>

<details><summary><b>Q100</b> · Ch 30 · advanced: What new problems do derived indexes bring?</summary>

Staleness and permission problems that a baseline index does not have. **[E]**

</details>

<details><summary><b>Q101</b> · Ch 30 · advanced: What did the pattern-selection exercise not show?</summary>

That the patterns perform. It showed the routing rules are consistent and the arithmetic is right; this repository has built none of them. **[X, N]**

</details>

<details><summary><b>Q102</b> · Ch 31 · foundational: Which decisions deserve an ADR?</summary>

Those affecting structure or key quality attributes, or hard to reverse [S215]. **[S215]**

</details>

<details><summary><b>Q103</b> · Ch 31 · intermediate: What did linting this repository's ADRs find?</summary>

No structural defects, and Accepted records that cite still-Proposed ones (ADR-002 and ADR-006), a human decision (OI-073). **[X]**

</details>

<details><summary><b>Q104</b> · Ch 31 · advanced: Why not fix that automatically?</summary>

Because the right response is a human decision about status informed by the evidence gaps, not a tool rewriting history. **[E]**

</details>

<details><summary><b>Q105</b> · Ch 13 · advanced: Your tenant-isolation design relies on a database filter. Name two ways it could still leak.</summary>

The identity setting the policy reads could be changed by the role (OI-069), and a cache or derived store (summaries, evaluation sets) could sit outside the policy. Test both. **[X, E]**

</details>

<details><summary><b>Q106</b> · Ch 20 · advanced: Quality fell after a cost cut. Which levers are the likely culprits and how do you diagnose?</summary>

Lower K, shallower rerank, quantization or smaller dimensions, cheaper model routing. Re-run the golden set by slice, compare paired intervals, and check returned counts under your filters. **[E]**

</details>

<details><summary><b>Q107</b> · Ch 18 · advanced: What stops evaluation itself from being a data leak?</summary>

Running it as a permission-aware, access-controlled part of the system with content-free reporting. **[E]**

</details>

<details><summary><b>Q108</b> · Ch 21 · advanced: Define recovery objectives for a RAG platform.</summary>

Per data class: raw objects are the source of truth, indexes are rebuildable, conversation data may differ; make the data path at-least-once and idempotent so rebuilds are safe, and rehearse. **[E]**

</details>
