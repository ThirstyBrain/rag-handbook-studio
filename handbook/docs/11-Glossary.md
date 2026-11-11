# Glossary

Cumulative. Terms are added as chapters complete. Chapter in brackets = where defined.

| Term | Definition |
|---|---|
| **ANN (approximate nearest neighbour)** | Search that trades exactness for speed when finding close vectors. [Ch. 5 — previewed in Ch. 2] |
| **BM25** | A lexical (sparse) ranking function over term statistics. Azure AI Search uses it for full-text scoring; the PostgreSQL docs reviewed do not mention it. [Ch. 2, 9] |
| **BPE (byte-pair encoding)** | Subword tokenization that iteratively merges the most frequent adjacent symbol pairs. [Ch. 2] |
| **Chunk** | A unit of text indexed and retrieved; carries provenance metadata. [Ch. 4] |
| **Context window** | Maximum tokens a model processes in one call. Capacity is not the same as effective utilisation. [Ch. 1] |
| **Corpus drift** | Change in the document/query population that erodes a previously tuned system. [Ch. 2] |
| **Cosine similarity** | Dot product divided by the product of norms; depends on direction only. [Ch. 2] |
| **Dense representation** | Short vector with all dimensions populated; an embedding. [Ch. 2] |
| **Dual encoder** | Two encoders (query, passage) mapping into one vector space. [Ch. 2] |
| **Embedding** | Fixed-length vector representing text in one model's space. [Ch. 2] |
| **Embedding drift** | Vectors becoming incomparable because the embedding model changed. [Ch. 2] |
| **Grounding** | Constraining an answer to supplied evidence; verified by citation and faithfulness checks, not assumed. [Ch. 1] |
| **Hallucination** | Plausible yet nonfactual generated content. [Ch. 1] |
| **halfvec** | pgvector 16-bit float vector type; indexable up to 4,000 dimensions (v0.8.7 docs). [Ch. 2] |
| **Long-context prompting** | Supplying large amounts of source text directly in the prompt instead of retrieving. [Ch. 1] |
| **Non-parametric memory** | Knowledge held in an external, updatable store (index). [Ch. 1] |
| **Parametric memory** | Knowledge encoded in model weights. [Ch. 1] |
| **RAG** | Retrieval-Augmented Generation: retrieve evidence at query time and constrain generation to it. [Ch. 1] |
| **RAG contract** | Authorized retrieval → delimited evidence → constrained generation → verifiable citations → audit record. [Ch. 1] |
| **Sparse representation** | Vocabulary-sized, mostly-zero representation, e.g. lexical term weights. [Ch. 2] |
| **Token** | Subword unit from a model's vocabulary; the unit of limits and billing. [Ch. 2] |
| **Chunker version** | Identifier of the chunking code+config that produced a chunk; changing it is a re-embedding event. [Ch. 4] |
| **Contextual retrieval** | Prepending chunk-specific context to each chunk before embedding and keyword indexing; published gains are vendor-reported. [Ch. 4] |
| **Context fragmentation** | Loss of meaning when cutting text (lost antecedents, detached headers, split tables). [Ch. 4] |
| **Dead-letter queue (DLQ)** | Sub-queue holding messages that could not be processed; needs operational monitoring and replay. [Ch. 3] |
| **Deletion propagation** | Ensuring a source deletion removes all derived chunks, caches and artifacts from the index. [Ch. 3] |
| **Heading path** | Ordered section titles leading to a chunk (e.g. `Policy > Parental leave`); used as metadata and prepended to embedding text. [Ch. 4] |
| **Idempotency (ingestion)** | Processing the same event twice yields the same state; achieved with content hashes, deterministic IDs and stage-then-swap. [Ch. 3] |
| **Late chunking** | Embedding a long text in one pass and pooling per chunk afterwards so chunk vectors carry document context. [Ch. 4] |
| **Layout analysis** | Extracting structural elements (paragraph roles, tables, figures, sections) from a document, not just text. [Ch. 3] |
| **Lineage (data)** | Recorded chain from source object through extractor, chunker and embedder versions to the indexed chunk. [Ch. 3] |
| **Overlap** | Text repeated between adjacent chunks to protect boundary-straddling facts; raises chunk count. [Ch. 4] |
| **Parent-child chunking** | Matching on small child chunks, returning larger parents to the generator. [Ch. 4, 14] |
| **Reconciliation** | Periodic full diff of source vs. index to repair missed events. [Ch. 3] |
| **Stage-then-swap** | Writing a new document version inactive, then activating it and retiring the old one atomically. [Ch. 3] |
| **Table-aware chunking** | Splitting tables between rows and repeating the header row in each piece. [Ch. 4] |
| **Binary quantization (BQ)** | Storing each vector dimension in 1 bit; shortlist by Hamming distance, then re-rank with original vectors. [Ch. 5] |
| **efSearch / ef_search** | HNSW query-time candidate list size; higher raises recall and latency. [Ch. 5] |
| **Filtered vector search** | ANN search restricted by metadata (tenant, ACL, date); the case where recall silently degrades. [Ch. 5] |
| **HNSW** | Hierarchical Navigable Small World: multi-layer proximity graph for ANN search. [Ch. 5] |
| **IVF (inverted file)** | ANN index that clusters vectors into lists and scans only the nearest `probes` lists. [Ch. 5] |
| **Iterative index scan** | pgvector (0.8.0+) feature that keeps scanning the index until enough rows pass the filter. [Ch. 5] |
| **Pre-filter / post-filter** | Applying the filter during ANN traversal vs. after the candidate list is produced. [Ch. 5] |
| **Probes** | Number of IVF lists scanned per query; probes = lists equals exact search. [Ch. 5] |
| **Product quantization (PQ)** | Lossy compression that quantizes vector sub-vectors against learned codebooks. [Ch. 5] |
| **Recall@k (ANN)** | Fraction of the true top-k (from exact search) that the approximate index returns. [Ch. 5] |
| **Re-ranking (quantized)** | Re-scoring an ANN shortlist using original full-precision vectors. [Ch. 5] |
| **Scalar quantization (SQ)** | Storing each dimension in fewer bits (e.g. int8). [Ch. 5] |
| **Shadow index** | A new index built alongside the live one, evaluated, then cut over to. [Ch. 2, 5] |
| **Tenant-per-shard** | Multi-tenancy pattern giving each tenant its own shard and vector index. [Ch. 5] |
| **BOLA (broken object-level authorization)** | Failure to verify that the caller owns the object id they request (e.g. a conversation id). [Ch. 7] |
| **Bulkhead (failure boundary)** | Isolation of a dependency's failure so it does not cascade (separate budgets, timeouts, fallbacks). [Ch. 7] |
| **Candidate generation** | The recall-oriented stage that returns `candidate_k` chunks from each retriever before fusion and reranking. [Ch. 6] |
| **Completeness / utilization** | Evaluation metrics: does the response answer all parts of the query / how much of the response comes from supplied chunks. [Ch. 6] |
| **Context assembly** | Selecting, de-duplicating, ordering, delimiting and budgeting retrieved chunks for the prompt. [Ch. 6, 7] |
| **Deterministic (standard) RAG** | Fixed pipeline: preprocess → retrieve → assemble → generate → validate; no runtime decisions about whether or how often to search. [Ch. 7] |
| **Edge ordering** | Placing the strongest chunks at the start and end of the context and weaker ones in the middle. [Ch. 6] |
| **Hit rate@K** | Fraction of queries with at least one relevant item in the top-K. [Ch. 6] |
| **MMR (Maximal Marginal Relevance)** | Greedy re-ranking trading query relevance against similarity to already-selected items to reduce redundancy. [Ch. 6] |
| **MRR (mean reciprocal rank)** | Mean over queries of 1/rank of the first relevant result. [Ch. 6] |
| **Mutation testing (as used here)** | Injecting a deliberate defect into code and confirming a test fails, to check the test has teeth. [Ch. 7] |
| **nDCG@K** | Normalised discounted cumulative gain: DCG divided by the ideal DCG; 0–1; needs graded relevance. [Ch. 6] |
| **Orchestrator** | The component that runs the online RAG pipeline with deadlines, budgets and identity propagation. [Ch. 7] |
| **Precision@K / Recall@K** | Share of top-K that is relevant / share of all relevant items found in top-K. [Ch. 6] |
| **Prompt caching (provider)** | Provider-side caching of an identical prompt prefix; stable content must come first. Pricing and limits are vendor-specific. [Ch. 7] |
| **RRF (Reciprocal Rank Fusion)** | Rank-based fusion: score(d) = Σ 1/(c + rank(d)) over result lists, c commonly 60. [Ch. 6] |
| **Semantic cache** | Cache hit decided by embedding similarity of queries; risks false hits and permission leakage. [Ch. 7] |
| **Trust boundary** | Line across which data or control passes between components of different trust (user, document, application, model). [Ch. 7] |
| **ABAC (attribute-based access control)** | Authorization decided by evaluating attributes of subject, object, operation and sometimes environment against policy (NIST SP 800-162). [Ch. 8] |
| **Analyzer** | Text-processing chain (tokenisation, case folding, stop words, stemming) applied identically to documents and queries in lexical search. [Ch. 9] |
| **BM25** | Lexical ranking: IDF × saturated term frequency with length normalisation; parameters k1 (default 1.2) and b (default 0.75) per Elastic's documentation. [Ch. 9] |
| **Group-id ACL** | Document ACL that lists group identifiers (resolved against the caller's current groups) rather than expanded user ids; revokes immediately. [Ch. 8] |
| **Hybrid search** | Lexical and dense retrieval run in parallel and fused into one ranking. [Ch. 9] |
| **IDF (inverse document frequency)** | Term weight that grows as the term appears in fewer documents; a collection-level statistic. [Ch. 9] |
| **Min–max normalisation** | Rescaling a score list to [0,1] using its minimum and maximum before combining lists; sensitive to outliers. [Ch. 9] |
| **OBO (on-behalf-of flow)** | OAuth 2.0 flow where a middle-tier API obtains a downstream token that carries the user's identity (delegated scopes only). [Ch. 8] |
| **PITR (point-in-time restore)** | Restoring a database to a moment within the backup retention period; the recovery path for user errors that HA replicates. [Ch. 8] |
| **Policy-to-filter equivalence test** | Property test asserting a compiled search filter and the reference policy evaluator agree on generated (user, document) pairs. [Ch. 8] |
| **RBAC** | Role-based access control: permissions granted to roles, roles to users. [Ch. 8] |
| **RLS (row-level security)** | Postgres per-row policies, default-deny once enabled; owners/superusers/BYPASSRLS bypass unless forced. [Ch. 5, 8] |
| **RPO / RTO** | Maximum tolerable data loss / time to restore service; define per data class. [Ch. 8] |
| **Relative score fusion** | Fusion that uses normalised scores (not ranks) from each leg; Weaviate's default since v1.24; exact normalisation not documented on the page read. [Ch. 9] |
| **Revocation window** | Time between a permission change at the source and its effect on retrieval; a security requirement, driven by sync design. [Ch. 8] |
| **Security filter (trimming)** | Query filter that excludes documents whose stored principal strings do not match the caller's identity; string comparison only. [Ch. 8] |
| **Tenant-placement catalog** | Mapping of each tenant to its service/index/region, used for routing and migration. [Ch. 8] |
| **Adaptive routing (Adaptive-RAG)** | Using a small classifier to choose between no retrieval, single-step retrieval and iterative retrieval per query complexity. [Ch. 10, 11] |
| **Compositionality gap** | Answering every sub-question correctly yet failing the composed question; does not shrink with model scale in the studied models. [Ch. 10, 11] |
| **Consensus bias** | In rank fusion, an irrelevant document that overlaps several variants ranks high because it appears in many lists. [Ch. 11] |
| **Context contamination** | A conversational rewriter importing the previous topic into a topic-switch query. [Ch. 10] |
| **Evidence chain** | Recorded sequence of (hop, query, retrieved ids/versions) behind an answer; used for audit and citations. [Ch. 11] |
| **Fan-out (multi-query)** | Generating several query variants, retrieving each in parallel, and fusing the lists. [Ch. 11] |
| **HyDE** | Embedding an LLM-written hypothetical answer document instead of the query. [Ch. 10] |
| **Multi-hop question** | A question whose answer needs evidence from several documents combined. [Ch. 11] |
| **PPR (Personalized PageRank)** | PageRank with restarts at seed nodes; used to spread relevance from query entities through a graph. [Ch. 11] |
| **Query augmentation** | Adding context to a short/vague query while keeping the original. [Ch. 10] |
| **Query decomposition** | Splitting a complex query into sub-queries, independent (parallel) or dependent (sequential). [Ch. 10, 11] |
| **Query expansion** | Adding terms or pseudo-documents to a query to bridge vocabulary gaps; gains shrink as the retriever gets stronger. [Ch. 10] |
| **Shortcut (benchmark)** | A way to answer a nominally multi-hop question without multi-hop reasoning; inflates apparent gains. [Ch. 11] |
| **Stop reason** | Recorded cause of loop termination: answer_found, no_new_evidence, max_hops, budget, reader_found_nothing. [Ch. 11] |
| **Visited set** | Set of already-seen evidence ids used to stop an iterative loop when a hop adds nothing new. [Ch. 11] |
| **Matryoshka Representation Learning (MRL)** | Training method producing coarse-to-fine embeddings usable at multiple sizes. [Ch. 2] |
| **Candidate recall@N** | Fraction of relevant documents present in the first-stage top N; the ceiling for any reranker. [Ch. 12] |
| **Cross-encoder** | Model that scores a query and a document as one joint input; accurate but not precomputable per pair. [Ch. 12] |
| **Late interaction** | Independent query/document encodings with token-level similarity (ColBERT-style); document vectors precomputed. [Ch. 12] |
| **Re-ranking** | Second-stage scoring of a short candidate list to improve ordering. [Ch. 12] |
| **Edge ordering** | Placing the strongest passages first and last in the prompt and the weakest in the middle; a heuristic to test. [Ch. 12] |
| **Abstention threshold** | Score cutoff below which the system declines to answer; must be calibrated per model. [Ch. 12] |
| **Selectivity (filter)** | Fraction of rows a predicate keeps; decides which execution plan and index strategy works. [Ch. 13] |
| **Iterative index scan** | pgvector mode that keeps scanning the ANN index until enough rows pass the filter or a limit is hit. [Ch. 13] |
| **Generic plan** | Prepared-statement plan made without parameter values; can choose the ANN index and starve selective filters. [Ch. 13] |
| **Self-query** | An LLM extracting metadata filters from a natural-language question; its output is untrusted. [Ch. 13] |
| **Mandatory predicates** | Tenant, ACL and not-deleted conditions built by trusted code and AND-ed outside any user filter. [Ch. 13] |
| **Parent-child retrieval** | Index small child chunks for matching and return their larger parent (or a window) for reading; also called small-to-big. [Ch. 14] |
| **Auto-merging** | Replacing several sibling hits by their parent once a threshold share of the parent's children is retrieved. [Ch. 14] |
| **Sentence window** | Returning the hit plus nearby neighbours within a token budget. [Ch. 14] |
| **Over-fetch (children)** | Retrieving more child chunks than the number of parents wanted because children cluster in few parents. [Ch. 14] |
| **RAPTOR** | Tree of recursively clustered and summarised chunks retrieved at several abstraction levels. [Ch. 14] |
| **Agentic RAG** | Retrieval in which a model chooses tool calls and next steps within code-owned limits. [Ch. 15] |
| **ReAct** | Pattern interleaving reasoning traces and tool actions. [Ch. 15] |
| **CRAG (corrective RAG)** | Evaluator-gated retrieval that picks answer, re-query or fallback by evidence quality. [Ch. 15] |
| **Self-RAG** | A trained model that retrieves on demand and critiques passages with reflection tokens. [Ch. 15] |
| **Excessive agency** | OWASP LLM06: damaging actions from excess functionality, permissions or autonomy. [Ch. 15] |
| **Tool allow-list** | Per-request set of tools the model may call; everything else is denied by the harness. [Ch. 15] |
| **MCP (Model Context Protocol)** | Protocol for discovering and invoking tools exposed by servers; standardises the wire, not trust. [Ch. 15] |
| **LLM gateway** | In-process component through which all model calls pass: routes, fallback chains, retries, breaker, sensitivity policy, budgets, cost estimates. [Ch. 16] |
| **Route (gateway)** | A named purpose (answer, rewrite, judge, embed) mapped by configuration to an ordered chain of provider/model targets. [Ch. 16] |
| **Embedding space** | A set of vectors produced by one model and dimensionality; vectors from different spaces must not share an index. [Ch. 16] |
| **Circuit breaker** | Stops calling a provider after repeated failures, then allows one trial call after a reset period. [Ch. 16] |
| **Locality (provider)** | local or external; restricted data may only go to local providers. [Ch. 16] |
| **Owner role / application role** | Separate database logins: the owner holds objects and runs migrations, the application role has data access only and cannot bypass row-level security. [Ch. 16] |
| **Transaction-scoped identity** | Caller identity written with a transaction-local database setting so it cannot survive into the next pooled request. [Ch. 16, 17] |
| **Fail closed (database)** | Policies raise an error when identity is missing instead of returning no rows, so a missing identity is loud. [Ch. 16] |
| **Migration checksum** | SHA-256 of an applied migration file, verified on each run so history cannot be edited silently. [Ch. 17] |
| **Guard test** | A test that fails any future table lacking required protections (here: forced RLS and policies). [Ch. 17] |
| **Object store (port)** | Abstraction for raw uploaded files with constructed, validated keys; filesystem adapter now, Azure Blob later. [Ch. 16] |
| **Content-addressed key** | Object key derived from the content hash (here within one document), so writes are idempotent and verifiable. [Ch. 16] |
| **Outbox** | A job recorded in the same transaction as the data change that requires it (for example object deletion), so the follow-up work cannot be lost. [Ch. 16] |
| **Lease (job)** | Time-limited claim on a job; if it expires the job can be claimed again, and only the holder can complete it. [Ch. 16] |
| **Dead job** | A job that used all its attempts; kept for inspection and never claimed again. [Ch. 16] |
| **SKIP LOCKED** | PostgreSQL locking option that lets concurrent consumers take different rows of a queue-like table without blocking. [Ch. 16] |
| **Staged version** | A document version whose raw file is stored but which is not yet searchable; chunking writes its chunks while it stays staged, and it becomes active only when indexing completes. [Ch. 16] |
| **Sandboxed extraction** | Parsing an untrusted file in a child process with no credentials, a timeout, an output cap and (on POSIX) resource limits, then validating its answer as untrusted data. [Ch. 16, 17] |
| **Column-level privilege** | A grant on specific columns of a table (for example reading ACL metadata but not content), used to give a worker a narrow path. [Ch. 17] |
| **PUBLIC policy trap** | A row-level-security policy created without a `TO` clause applies to every role, including roles added later; permissive policies are OR-ed, so it silently widens narrower policies. [Ch. 17] |
| **Structure-aware chunking** | Chunking that respects sections, sentences, code lines and table rows, repeats a table's header row when a table continues, and carries the section path with each chunk. [Ch. 4, 16] |
| **Permanent failure** | A job failure that retrying cannot fix (for example an encrypted PDF); the job ends at once and the reason is recorded as a short safe code. [Ch. 16] |
| **Golden dataset** | A versioned set of evaluation cases (query, identity, graded relevant documents with locators, reference facts, answerable flag, slice tags, provenance) with known-good expectations. Keyed to document plus locator, never chunk ids. [Ch. 18] |
| **Recall@K** | Relevant documents in the top K divided by all relevant documents (not by the number retrieved). [Ch. 18] |
| **Precision@K** | Relevant documents in the top K divided by K; a short list is penalised. [Ch. 18] |
| **MRR (mean reciprocal rank)** | Mean over queries of 1/rank of the first relevant document, 0 if none. [Ch. 18] |
| **nDCG@K** | Discounted cumulative gain of a ranking divided by that of the ideal ranking over all judged documents; uses graded relevance. [Ch. 18] |
| **Context precision** | Rank-aware precision of retrieved context: sum of precision@k times relevance at rank k, over relevant items in the top K (Ragas definition). [Ch. 18] |
| **Faithfulness (groundedness)** | Share of claims in an answer that are supported by the retrieved context. An answer with no claims has no score. [Ch. 18] |
| **Citation accuracy** | Counted as three failures: phantom (cites something never retrieved), unsupported (cited chunk does not support the claim) and uncited. [Ch. 18] |
| **Cohen's kappa** | Agreement between two raters corrected for the agreement expected by chance; a constant judge on skewed data has high raw agreement and kappa 0. [Ch. 18] |
| **Position bias** | An LLM judge's tendency to favour an answer because of the order in which it is shown; reduced by judging both orders and counting only consistent wins. [Ch. 18] |
| **Paired bootstrap** | Resampling queries while keeping each query's two system scores together, to get an interval for the difference between two versions. [Ch. 18] |
| **Regression gate** | A release check returning regression, inconclusive or improvement from the interval of a paired difference; inconclusive is not a pass. [Ch. 18] |
| **Slice** | A tagged segment of the evaluation set (language, document type, tenant tier, query type) reported separately so an average cannot hide a regression. [Ch. 18] |
| **GenAIOps / LLMOps** | Operational practice for prompting and RAG systems: versioning prompts, orchestrators, chunking pipelines and indexes, evaluation, gateway-based rollout, monitoring and feedback. [Ch. 19] |
| **Release bundle** | Everything that determines behaviour: code, prompts, model ids and settings, chunker and extractor versions, embedding space and recipe, index parameters, reranker, judge and golden-set versions. [Ch. 19] |
| **SLI / SLO / error budget** | A measured ratio of good to valid events; its target over a window; and the allowed share of failures (1 minus the SLO). [Ch. 19] |
| **Burn rate** | How many times faster than 'exactly on budget' the error budget is being consumed: error ratio divided by (1 minus the SLO). [Ch. 19] |
| **Multiwindow, multi-burn-rate alert** | An alert that requires both a long and a short window to exceed a burn rate, so it is precise, scales with severity and resets quickly; several such rules cover fast and slow burns. [Ch. 19] |
| **Wilson score interval** | An interval for a proportion that behaves well for small counts; used to alert only when the lower bound of a sampled failure rate exceeds the threshold. [Ch. 19] |
| **Canary query** | A fixed golden case run on a schedule through the real pipeline to detect retrieval or model regressions quickly. [Ch. 19] |
| **Content capture** | Recording prompts, messages or outputs in telemetry; off by default in OpenTelemetry GenAI guidance, enabled only by explicit opt-in. [Ch. 19] |
| **Label cardinality** | The number of distinct values of a metric label; identifiers as labels explode series counts and cost. [Ch. 19] |
| **Recall (ANN)** | Share of the exact top-K neighbours that an approximate index returns; measured against an exact scan. [Ch. 20] |
| **ef_search** | pgvector HNSW query parameter: size of the candidate list during search; higher gives more recall and more latency (default 40). [Ch. 20] |
| **Iterative index scan** | pgvector option (strict_order or relaxed_order) that keeps scanning an approximate index until enough rows pass a filter; fixes under-delivery of filtered ANN queries at a latency cost. [Ch. 20] |
| **Scalar / binary quantization** | Storing vector components in fewer bits (for example int8 or one bit) to cut storage and speed search, usually with oversampling and re-scoring using the original vectors. [Ch. 20] |
| **Matryoshka embedding** | An embedding trained so that truncated prefixes remain usable at lower dimensions. [Ch. 20] |
| **Prompt caching** | Provider feature that reuses the processed static prefix of a prompt; writes and reads are priced at multiples of the base input price; retrieved chunks are generally not cacheable. [Ch. 20] |
| **Tail amplification** | Growth of the chance that at least one of n parallel calls is slow: 1 minus (1 minus p) to the n. [Ch. 20] |
| **Hedged request** | Sending a duplicate of a call after a delay and taking the first answer, to cut tail latency; only for idempotent reads and not under overload. [Ch. 20] |
| **Little's law** | Average requests in flight equal arrival rate times time in system; used to size pools and workers. [Ch. 20] |
| **Deadline propagation** | Passing the caller's remaining time to each downstream call so the worst case equals the caller's deadline, not the sum of per-call timeouts. [Ch. 21] |
| **Retry budget** | A limit on retries as a fraction of traffic (for example a token bucket) so retries cannot overload a degraded dependency. [Ch. 21] |
| **Retry storm / amplification** | Multiplication of attempts when several layers each retry; five layers of three retries can multiply load 243 times. [Ch. 21] |
| **Metastable overload** | A state in which wasted work (serving requests whose clients have given up) keeps a system overloaded after the original trigger has ended. [Ch. 21] |
| **Load shedding** | Rejecting or dropping excess or expired work early to protect capacity and latency. [Ch. 21] |
| **Thundering herd** | Many clients retrying or waking at the same instant; reduced by jitter. [Ch. 21] |
| **Circuit breaker** | A closed, open or half-open state machine that stops calls to a failing dependency and probes for recovery. [Ch. 21] |
| **Degradation ladder** | An ordered set of reduced-capability modes (skip rerank, lexical-only, fallback model, passages without generation, explicit unavailable), each evaluated in advance and each keeping every security control. [Ch. 21] |
| **RPO / RTO** | Recovery point objective (tolerable data loss, as time) and recovery time objective (tolerable downtime). [Ch. 21] |
| **PITR (point-in-time recovery)** | Restoring a PostgreSQL cluster from a base backup and archived WAL to a chosen moment; restores the whole cluster only. [Ch. 21] |
| **Indirect prompt injection** | Instructions planted in content an LLM application retrieves or processes (documents, web pages, emails, tool output), so an attacker needs no access to the user interface. [Ch. 22] |
| **Trust boundary** | A place where data crosses from one trust level to another and must be validated, authorised or isolated; the basis of the data-flow threat model. [Ch. 22] |
| **STRIDE** | Six threat categories used to enumerate threats per component: spoofing, tampering, repudiation, information disclosure, denial of service, elevation of privilege. [Ch. 22] |
| **Egress control** | A deterministic policy on model output that removes channels for data to leave or code to run: images, HTML, non-allow-listed links, URLs with queries. [Ch. 22] |
| **Parser differential** | A bypass that works because the security check and the real client parse the same input differently (for example backslashes or userinfo in URLs). [Ch. 22] |
| **Evidence framing** | Wrapping retrieved text in escaped blocks with a per-request nonce so it cannot forge prompt structure; hygiene, not an injection defence. [Ch. 22] |
| **Lethal trifecta** | The combination of access to private data, exposure to untrusted content and external communication in one system; avoid combining all three. [Ch. 22] |
| **Post-retrieval access re-check** | A fail-closed verification, after retrieval, that every chunk entering a prompt belongs to the caller's tenant and ACL; an empty ACL means nobody. [Ch. 22] |
| **Knowledge-base poisoning** | Planting texts in the corpus to steer answers to chosen questions; ingestion is therefore a security boundary. [Ch. 22] |
| **Denial of wallet** | Abuse that drives up pay-per-use cost through many or large requests; bounded by input caps, rate limits and budgets checked before admission. [Ch. 22] |
| **Luhn check** | Checksum used to avoid redacting digit runs that are not card numbers. [Ch. 22] |
| **AI system register** | A versioned inventory of AI systems with owner, purpose, data classes, pinned models, risk tier, impact-assessment status, oversight, evidence, retention and review date. [Ch. 23] |
| **NIST AI RMF / Generative AI Profile** | A voluntary risk framework (functions Govern, Map, Measure, Manage) and its profile naming twelve generative-AI risks (NIST AI 600-1). [Ch. 23] |
| **Risk acceptance** | A recorded decision not to mitigate a risk, with rationale, owner and an expiry date; an expired acceptance is a finding. [Ch. 23] |
| **DPIA** | Data protection impact assessment (GDPR Article 35): required where processing is likely to result in high risk, with minimum content defined. [Ch. 23] |
| **Erasure propagation** | Applying a deletion to every store that holds a copy (raw objects, chunks, vectors, caches, evaluation sets, logs) and stating the residual window for backups. [Ch. 23] |
| **Policy as code** | Governance rules implemented as automated checks (register validation, framework coverage, expiry) that run in CI and produce evidence. [Ch. 23] |
| **Hash-chained audit log** | A log whose entries each hash their content and the previous hash, making edits, deletions and reordering detectable; needs an externally anchored head hash against a full rewrite. [Ch. 23] |
| **Synced vs federated connector** | A synced connector copies and indexes source content (and permissions) into your index; a federated connector fetches at query time with no data movement, leaving the source authoritative but limiting ranking control. [Ch. 24] |
| **Permission sync** | Keeping the index's copy of access rules in step with the source; a distinct problem from content sync because permissions change without the content changing. [Ch. 24] |
| **Change feed / delta token** | A pull mechanism returning changes since a stored token; it can replay changes, expire tokens (forcing a full resync) and lag. [Ch. 24] |
| **Inherited ACL** | Permissions a file receives from its folder; a folder change is logged on the folder only, so children must be re-snapshotted. [Ch. 24] |
| **Over-exposure / under-exposure** | Over-exposure: the index allows what the source no longer permits (a leak). Under-exposure: the index hides what the source permits (a lost answer). [Ch. 24] |
| **Staleness bound (fail closed)** | A limit on time since the last successful permission sync, after which the query path refuses or restricts results. [Ch. 24] |
| **Reconciliation drift** | The number of documents whose index state differs from the source in a periodic full comparison; the real correctness metric of a connector. [Ch. 24] |
| **Agent assist** | A support-bot stage where the model drafts cited answers for a human agent, who edits and sends; the safest starting point. [Ch. 25] |
| **Containment vs resolution** | Containment: no human involved. Resolution: the problem was solved. Abandonment inflates containment; vendors define and redefine these terms. [Ch. 25] |
| **Verified resolution** | A bot-handled conversation confirmed as correct and satisfactory by sampled review, a validated judge or outcome signals. [Ch. 25] |
| **Commitment guard** | A deterministic rule allowing a sentence that commits the company (refund, guarantee, deadline) only if it appears verbatim in the cited policy; otherwise hand off. [Ch. 25] |
| **High-risk intent** | A request class (refunds, legal, safety, account closure) that always goes to a human, with the classifier biased toward over-flagging. [Ch. 25] |
| **Handoff packet** | The context passed from bot to human: conversation id, intent, cited sources, the bot's draft and a customer identity reference. [Ch. 25] |
| **Citation verification** | Checking each reference against an authoritative index: DOI lookup with metadata comparison, fuzzy matching without a DOI, an ambiguity band for humans, field-level errors and retraction status. [Ch. 26] |
| **Render references from metadata** | The model emits retrieved source identifiers and code renders the bibliography from index metadata, so a citation cannot be non-existent or garbled. [Ch. 26] |
| **DOI swap** | A fabricated citation that carries a valid DOI belonging to a different work; caught by comparing the cited title with the DOI's record. [Ch. 26] |
| **Retraction Watch data** | A database of retractions, corrections and expressions of concern, exposed through Crossref (and OpenAlex's is_retracted flag). [Ch. 26] |
| **GROBID** | A machine-learning tool converting scholarly PDFs into structured TEI (header, references, full text, citation contexts, figures and tables). [Ch. 26] |
| **Citation context** | The sentence around an in-text citation, stating what one paper says about another; a useful retrieval unit. [Ch. 26] |
| **AST-based chunking** | Chunking source code along syntax-tree units (functions, methods, class headers, statement runs) with a size cap and statement-boundary splits. [Ch. 27] |
| **Chunk partition invariant** | Every line of a file belongs to exactly one chunk and every chunk ends at a statement boundary; checked in CI for code chunkers. [Ch. 27] |
| **Cut rate** | The share of chunks with a boundary strictly inside a function body; 73.7% for 40-line windows versus 3.0% for AST units on this repository. [Ch. 27] |
| **Query leakage** | An evaluation flaw where the query text is present in the indexed corpus (for example docstrings), inflating retrieval scores. [Ch. 27] |
| **Symbol index** | An index of definitions, references, imports and call edges used to answer structural questions and expand retrieved code. [Ch. 27] |
| **Package hallucination** | A code model recommending a dependency that does not exist, enabling package-confusion supply-chain attacks. [Ch. 27] |
| **tree-sitter** | An incremental, error-tolerant parsing library with parsers for many languages. [Ch. 27] |
| **Image verbalisation** | Using a vision-language model at ingestion to write a text description of each figure, stored and embedded as text; costs a model call per image and supports citable captions. [Ch. 28] |
| **Late-interaction page retrieval** | Embedding page images into many vectors and matching a query against them token by token (ColPali style), avoiding text extraction at the cost of large multi-vector storage. [Ch. 28] |
| **Visual token** | The unit of image cost for a vision model; one vendor's rule is ceil(width/28) times ceil(height/28) per image, capped by tier. [Ch. 28] |
| **Caption linking** | Attaching a figure or table to its caption by type, column, direction and one-to-one assignment, and to the paragraphs that mention its label. [Ch. 28] |
| **Region / time locator** | A citation target inside a medium: a page bounding region for documents or a time range for audio and video. [Ch. 28] |
| **Transcript hallucination guard** | Flagging transcript segments whose time span has almost no audible speech so invented text is quarantined. [Ch. 28] |
| **Derived-text provenance label** | A marker naming the modality, source and untrusted status of text recovered from media, with escaping so it cannot close its own block. [Ch. 28] |
| **Semantic layer** | A governed definition of business metrics and dimensions that all consumers query, so numbers agree and a model composes metric queries instead of free SQL. [Ch. 29] |
| **Guarded SQL execution** | Running untrusted SQL as a restricted role with column grants, row-level security, a read-only transaction, a timeout and a row cap, all enforced by the database. [Ch. 29] |
| **Tenant-setting attack** | A SELECT that calls set_config to change the per-transaction setting a row-level-security policy reads; closed by revoking EXECUTE on set_config from the role. [Ch. 29] |
| **Execution accuracy** | Judging generated SQL by comparing result sets with the gold query's (multiset, ordered only if the gold orders), ideally on several datasets built to distinguish wrong queries. [Ch. 29] |
| **Degenerate test data** | Data on which different queries return the same rows (for example one order per customer), so execution accuracy on it accepts wrong SQL. [Ch. 29] |
| **Modular RAG** | A pipeline treated as a graph of replaceable operators with routing between alternative paths per query, rather than one fixed sequence. [Ch. 30] |
| **Self-Route** | Sending each query either to retrieval or to a long-context prompt based on the model's own self-reflection; the fallback pays for both attempts. [Ch. 30] |
| **Break-even fraction** | The share of queries retrieval must answer for routing to cost no more than always using the long prompt: retrieval cost divided by long-prompt cost. [Ch. 30] |
| **Community summary** | A pregenerated summary of a group of closely related entities in a knowledge graph, combined into partial answers for global questions. [Ch. 30] |
| **Summary tree** | A hierarchy built by recursively clustering and summarising chunks so retrieval can choose a level of abstraction (RAPTOR style). [Ch. 30] |
| **Personalized PageRank** | A graph-ranking algorithm biased toward query-relevant nodes, used by HippoRAG for single-step multi-hop retrieval. [Ch. 30] |
| **Pattern shopping** | Combining every retrieval technique into one pipeline without evidence that each earns its place. [Ch. 30] |
| **Architecture decision record (ADR)** | A short repository document recording one significant decision, its context, options, outcome and consequences. [Ch. 31] |
| **Decision log** | The collection of a project's ADRs. [Ch. 31] |
| **Superseded** | ADR status meaning a later record replaces this one; both name each other and the old one is kept. [Ch. 31] |
| **Append-only log** | The discipline of never rewriting an accepted decision: change it by writing a new record, or by a dated amendment. [Ch. 31] |
| **ADR confirmation** | A stated way to verify compliance with a decision, such as a review or a test (MADR). [Ch. 31] |
| **ADR rot** | Loss of trust in a decision log through stale statuses, silent edits, dangling links or decisions that were never recorded. [Ch. 31] |
