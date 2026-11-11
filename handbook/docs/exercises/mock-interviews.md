# Mock Interview Sheets

> GENERATED FILE from `docs/chapters/32-system-design-interview-preparation.md` (17 scenarios). Prompt, probes and scoring focus are verbatim from the chapter; the session plan below is an engineering suggestion **[E]**, not a measured or sourced norm. Rebuild: `python -I scripts/build-interview-pack.py`.

## How to run a session

1. Interviewer reads only **Prompt**; candidate asks clarifying questions (check against **Clarify first**).
2. Candidate states the security boundary and a sizing approach, then the architecture (method: Chapter 32.4).
3. Interviewer uses **Probes** one at a time; after the session, score against the rubric (Chapter 32.5) weighting the **Scoring focus**.
4. Compare with the model answer in the scenario (Chapter 32.6) and read the chapters in **Draws on**.

## SD-01 — Internal HR Policy Assistant

**Prompt.** An 8,000-person company wants an assistant that answers HR policy questions from about 400 policy documents, with citations. One country, one language.

**Probes.** "Why not just paste everything into the prompt?" "How do you know the answer is grounded?" "What if two policies conflict?"

**Scoring focus.** Architecture fit (not over-building), evaluation.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** How large is the corpus in tokens, how often do policies change, are any documents restricted by role or country, what happens when the answer is not in the policy (escalate to HR?), and what is the budget?

**Draws on.** Chapters 1, 4, 7, 9, 18, 30.

</details>

## SD-02 — Multi-Tenant SaaS Knowledge Assistant

**Prompt.** A B2B SaaS product adds an assistant over each customer's uploaded documents. There are 10,000 tenants; a few have millions of chunks, most have a few thousand.

**Probes.** "Show me where cross-tenant retrieval is made impossible." "What does your monitoring say when a tenant gets 3 of 10 results?" "How do you offboard a tenant?"

**Scoring focus.** Security and isolation, retrieval depth.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Tenant size distribution, residency, any per-tenant encryption keys, noisy-neighbour tolerance, delete-on-offboarding requirement, and whether tenants may share content.

**Draws on.** Chapters 5, 7, 8, 13, 29; ADR-013; OI-069.

</details>

## SD-03 — Permission-Aware Enterprise Search Across Wikis and Drives

**Prompt.** Build an assistant over Confluence, SharePoint and a shared drive. Users must only see answers derived from documents they may read. Permissions change daily.

**Probes.** "A user is removed from a group at 9:00. When does the assistant stop quoting their documents?" "How do you prove it?"

**Scoring focus.** Security and isolation, operations.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Which sources, synced or federated access, how stale a permission may be, how groups are nested, what to do with content whose permissions cannot be mapped, and the audit requirement.

**Draws on.** Chapters 8, 24, 30.

</details>

## SD-04 — Public Customer Support Chatbot

**Prompt.** A retailer wants a website chatbot to deflect support tickets, answering from help articles and order policies.

**Probes.** "What is your containment number and why do you distrust it?" "What does the bot do when the policy is silent?"

**Scoring focus.** Evaluation, security, trade-offs.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Which intents are high risk (refunds, legal, safety), what the bot may commit to, the handoff channel, disclosure obligations, the public audience's hostility, and how success is defined.

**Draws on.** Chapters 18, 22, 25.

</details>

## SD-05 — Research Assistant With Trustworthy Citations

**Prompt.** Lawyers or scientists want answers with references to papers or cases. A fabricated reference is unacceptable.

**Probes.** "How do you detect a citation that exists but does not support the claim?" "Who sees the verifier's rejections?"

**Scoring focus.** Evaluation, retrieval depth.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Closed or open corpus, whether the model may cite outside the index, licensing of the content, tolerance for "I cannot support that", and how citations are checked today.

**Draws on.** Chapters 9, 12, 18, 26.

</details>

## SD-06 — Codebase Assistant

**Prompt.** Engineers want to ask questions about a 5-million-line monorepo and get answers with file and line citations.

**Probes.** "How would you evaluate this without leaking the answer into the query?" "How do you handle a monorepo with per-directory ownership?"

**Scoring focus.** Retrieval depth, evaluation.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Languages, repository permissions, update frequency, whether answers may suggest code, secret and licence policy, and IDE versus chat.

**Draws on.** Chapters 4, 18, 27.

</details>

## SD-07 — Natural-Language Questions Over the Data Warehouse

**Prompt.** Business users want to ask "revenue by region last quarter" in English.

**Probes.** "Why execute the SQL during evaluation?" "Where does the model's authority end?"

**Scoring focus.** Security, evaluation.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Are there governed metrics, how many tables, who may see which rows and columns, tolerance for a wrong number, and who owns the semantic layer.

**Draws on.** Chapters 22, 29, 30; OI-069.

</details>

## SD-08 — Multimodal Technical-Manual Search

**Prompt.** Field engineers search PDF manuals full of diagrams, tables and photos.

**Probes.** "When would you not use a vision model?" "How do you cite part of a page?"

**Scoring focus.** Retrieval depth, trade-offs.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Share of content in figures and tables, need to cite page regions, device constraints, languages, and the cost budget.

**Draws on.** Chapters 3, 22, 28.

</details>

## SD-09 — The Bill Doubled

**Prompt.** Monthly model and infrastructure cost has doubled with no change in traffic. Find and fix it.

**Probes.** "What do you look at first?" "How do you know the cheaper path did not hurt quality?"

**Scoring focus.** Operations, evaluation.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Cost breakdown by component, token counts per request over time, cache hit rate, recent releases, and quality constraints.

**Draws on.** Chapters 11, 15, 18, 20, 21.

</details>

## SD-10 — Quality Dropped After an Embedding Upgrade

**Prompt.** A team upgraded to a newer embedding model and users report worse answers.

**Probes.** "How would you have caught this before release?" "What is your rollback?"

**Scoring focus.** Evaluation, operations.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Was the whole corpus re-embedded, are query and document vectors from the same model, what changed in dimensions or normalisation, and what evaluation existed before.

**Draws on.** Chapters 2, 5, 18, 20; ADR-012, ADR-017; OI-054.

</details>

## SD-11 — A Prompt-Injection Incident

**Prompt.** A user uploaded a document that caused the assistant to reveal another user's information in a link. Respond and redesign.

**Probes.** "What would have limited this to zero leaked bytes?" "How do you test your defences?"

**Scoring focus.** Security and isolation.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** What data left, through what channel, which controls existed, whether logs contain content, and the notification obligations.

**Draws on.** Chapters 19, 22, 23.

</details>

## SD-12 — Right to Erasure and Retention

**Prompt.** A customer requests deletion of all their personal data, including from the assistant. Design the process.

**Probes.** "List every place the data lives." "How do you prove it is gone?"

**Scoring focus.** Security, operations.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Which jurisdictions, what stores hold derived data, backup and log retention, how long deletion may take, and who signs off.

**Draws on.** Chapters 3, 14, 23; ADR-014, ADR-015.

</details>

## SD-13 — A 2-Second p95 Budget

**Prompt.** The product requires p95 end-to-end under 2 seconds, with hybrid retrieval, reranking and a streamed answer.

**Probes.** "What do you drop first under load?" "Where does the 2 seconds go?"

**Scoring focus.** Operations, trade-offs.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Time to first token or full answer, region, concurrency, which components are optional, and acceptable degradation.

**Draws on.** Chapters 6, 12, 20, 21.

</details>

## SD-14 — Multi-Hop Questions Over Reports

**Prompt.** Analysts ask questions such as "which suppliers of the delayed project also supply the other flagged project?" Single-pass retrieval misses the second fact.

**Probes.** "Why not make it an agent?" "How do you stop it looping?"

**Scoring focus.** Retrieval depth, architecture fit.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** How common multi-hop questions are, the latency tolerance, the structure of the data, and the cost of a wrong answer.

**Draws on.** Chapters 10, 11, 15, 30.

</details>

## SD-15 — Regional Outage and Disaster Recovery

**Prompt.** The primary region is down for hours. What happens to the assistant, and what should have been prepared?

**Probes.** "Which store do you restore first?" "What is your actual RTO, and how do you know?"

**Scoring focus.** Operations.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** The recovery time and recovery point objectives per data class, regulatory residency, and whether degraded service is acceptable.

**Draws on.** Chapters 3, 7, 21; OI-058.

</details>

## SD-16 — Choosing the Vector Store

**Prompt.** The team must choose between Postgres with pgvector and a managed vector search service.

**Probes.** "What would make you move off Postgres?" "Show me the decision record."

**Scoring focus.** Trade-offs and evolution.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Corpus size, filter and tenancy patterns, hybrid needs, team skills, residency, and budget.

**Draws on.** Chapters 5, 13, 20, 31; ADR-001.

</details>

## SD-17 — An Evaluation Program From Zero

**Prompt.** A team ships a RAG feature with no golden set and no metrics. Build the evaluation program.

**Probes.** "How many queries do you need to detect a 3-point change?" "How do you trust the judge?"

**Scoring focus.** Evaluation.

<details><summary>Interviewer notes: expected clarifying questions and chapters</summary>

**Clarify first.** Query sources, who can label, the risk profile, release cadence, and how permissions affect what a query may retrieve.

**Draws on.** Chapters 18, 19; OI-056.

</details>
