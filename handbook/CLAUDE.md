# CLAUDE.md
# Production-Grade RAG Architecture Handbook
## Repository Operating System, Engineering Standards & Execution Governance

---

# 1. PROJECT IDENTITY

## Project Name

**The Production-Grade RAG Architecture & Engineering Handbook**

Subtitle:

From Fundamentals to Enterprise-Scale Intelligent Retrieval Systems

## Project Mission

Create a comprehensive, research-backed, implementation-oriented technical handbook that enables experienced Software Architects, Solution Architects, Technical Leads, Principal Engineers, and AI Platform Architects to independently design, implement, evaluate, secure, optimize, and operate production-grade Retrieval-Augmented Generation systems.

This is not a generic AI tutorial.

This repository must become a long-term engineering reference containing:

- Deep technical explanations.
- Enterprise architecture patterns.
- Production-grade implementation.
- Architecture decision records.
- Engineering trade-offs.
- Real-world scenarios.
- Security and governance.
- Evaluation and observability.
- Performance and cost optimization.
- Architecture diagrams.
- Interview preparation.
- Technical references.

## Primary Reader Persona

The reader is an experienced enterprise software professional with approximately 13 years of engineering and architecture experience.

The reader understands:

- Distributed systems.
- Microservices.
- Event-driven architecture.
- REST APIs.
- Azure.
- .NET.
- Databases.
- CI/CD.
- Enterprise security.
- System design.
- Production reliability.
- Multi-tenant SaaS.

The reader wants to develop advanced expertise in:

- Enterprise AI Architecture.
- RAG Architecture.
- AI Platform Engineering.
- LLMOps.
- Agentic Systems.
- Production AI Engineering.

Teach at an intermediate-to-expert level.

Do not waste time explaining introductory programming concepts.

Prioritize architecture reasoning, implementation correctness, production engineering, and trade-off analysis.

---

# 2. CORE OPERATING PRINCIPLES

Claude Code MUST follow these principles throughout the project.

## 2.1 Research Before Authoring

Never begin a technical chapter by relying exclusively on model knowledge.

Research the topic using authoritative, current sources.

Verify:

- Technical capabilities.
- API behavior.
- Architecture patterns.
- Technology versions.
- Limitations.
- Security considerations.
- Production deployment requirements.

## 2.2 Architecture Before Implementation

Before implementing a major capability:

1. Identify the problem.
2. Define requirements.
3. Define constraints.
4. Evaluate alternatives.
5. Select the architecture.
6. Document the decision.
7. Implement.
8. Test.
9. Validate.
10. Document operational behavior.

## 2.3 Evidence Before Claims

Never fabricate:

- Documentation.
- Citations.
- Benchmarks.
- Performance numbers.
- Production case studies.
- API capabilities.
- Test results.
- Security guarantees.

If a claim cannot be verified, label it appropriately.

## 2.4 Incremental Execution

Never generate the entire handbook or application in a single uncontrolled pass.

Work in bounded, verifiable milestones.

For handbook authoring:

- Research and write 2–3 chapters per batch.
- Complete the chapters before moving forward.
- Validate technical consistency.
- Update progress tracking.
- Preserve completed work.

For implementation:

- Implement one coherent capability at a time.
- Test it before proceeding.
- Maintain a working application.
- Avoid accumulating unverified code.

## 2.5 Production Engineering Over Toy Examples

Every important implementation must reflect real engineering concerns.

Consider:

- Security.
- Reliability.
- Scalability.
- Maintainability.
- Observability.
- Performance.
- Cost.
- Data lifecycle.
- Failure recovery.
- Operational ownership.

Simplifications are allowed only when clearly identified.

## 2.6 Explain Trade-offs

Every significant architectural recommendation must explain:

- Why it is selected.
- What alternatives exist.
- What trade-offs are accepted.
- When the decision should be reconsidered.

Do not present one technology or pattern as universally superior.

---

# 3. REPOSITORY STRUCTURE

Maintain the following repository structure.

```text
rag-architecture-handbook/
│
├── CLAUDE.md
├── README.md
├── CHANGELOG.md
├── .gitignore
│
├── project-management/
│   ├── MASTER-PRD.md
│   ├── MASTER-TOC.md
│   ├── EXECUTION-PLAN.md
│   ├── PROGRESS.md
│   ├── RESEARCH-REGISTER.md
│   ├── QUALITY-REPORT.md
│   ├── OPEN-ISSUES.md
│   └── MILESTONES.md
│
├── docs/
│   ├── RAG-Architecture-Handbook.md
│   ├── 00-Executive-Overview.md
│   ├── 01-RAG-Fundamentals.md
│   ├── 02-RAG-Architecture.md
│   ├── 03-Advanced-RAG.md
│   ├── 04-Production-Implementation.md
│   ├── 05-Security-and-Governance.md
│   ├── 06-Evaluation-and-LLMOps.md
│   ├── 07-System-Design-Interview-Guide.md
│   ├── 08-Interview-Question-Bank.md
│   ├── 09-Architecture-Decision-Records.md
│   ├── 10-Production-Readiness-Checklist.md
│   ├── 11-Glossary.md
│   ├── 12-References.md
│   │
│   ├── chapters/
│   ├── cheat-sheets/
│   ├── flashcards/
│   ├── exercises/
│   └── assets/
│       ├── diagrams/
│       ├── images/
│       └── attribution/
│
├── reference-implementation/
│   ├── README.md
│   ├── backend/
│   ├── frontend/
│   ├── database/
│   ├── infrastructure/
│   ├── tests/
│   ├── evaluation/
│   ├── observability/
│   ├── docker/
│   ├── scripts/
│   ├── .env.example
│   └── docker-compose.yml
│
├── adr/
│   ├── ADR-001-Technology-Selection.md
│   ├── ADR-002-Embedding-Strategy.md
│   ├── ADR-003-Chunking-Strategy.md
│   ├── ADR-004-Retrieval-Architecture.md
│   └── ...
│
├── scripts/
│   ├── validate-docs
│   ├── validate-links
│   ├── validate-diagrams
│   └── build-handbook
│
└── output/
    ├── RAG-Architecture-Handbook.pdf
    └── interview-preparation/
```

Adapt the structure when necessary, but preserve the separation between:

1. Handbook documentation.
2. Reference implementation.
3. Project management.
4. Architecture decisions.
5. Final deliverables.

Do not mix application source code into documentation directories.

Do not mix temporary research notes into the canonical handbook.

---

# 4. EXECUTION PLAN AND MILESTONES

Execute the project through the following milestones.

## M0 — Project Initialization

Deliver:

- Repository structure.
- Master PRD.
- Master table of contents.
- Execution plan.
- Progress tracker.
- Research register.
- Quality criteria.
- Technology selection proposal.

Do not start large-scale authoring before establishing the project structure.

## M1 — Research and Architecture

Deliver:

- Research inventory.
- Source verification.
- Reference architecture.
- Technology comparison.
- Initial ADRs.
- Diagram inventory.
- Implementation roadmap.

## M2 — RAG Fundamentals

Research and write 2–3 chapters per batch.

Topics:

- Traditional LLM vs. RAG.
- Embeddings.
- Document ingestion.
- Chunking.
- Vector databases.

## M3 — Retrieval and Architecture

Research and write 2–3 chapters per batch.

Topics:

- Retrieval mechanisms.
- RAG architecture.
- Enterprise architecture.
- Multi-tenancy.
- Hybrid search.

## M4 — Advanced RAG

Research and write 2–3 chapters per batch.

Topics:

- Query rewriting.
- Multi-query retrieval.
- Multi-hop retrieval.
- Reranking.
- Metadata filtering.
- Parent-child retrieval.
- Agentic RAG.

## M5 — Reference Implementation

Build the application incrementally.

The application must remain separate under:

`reference-implementation/`

Implement:

1. Project foundation.
2. Database schema.
3. Document ingestion.
4. Extraction and chunking.
5. Embeddings.
6. Vector indexing.
7. Hybrid retrieval.
8. Metadata filtering.
9. Reranking.
10. Context assembly.
11. Grounded generation.
12. Citation validation.
13. Authentication.
14. Tenant isolation.
15. Frontend.
16. Observability.
17. Evaluation.
18. Security.
19. Infrastructure.
20. CI/CD.

## M6 — Production Engineering

Complete:

- Reliability.
- Performance.
- Security.
- Evaluation.
- Monitoring.
- Cost optimization.
- Deployment.
- Failure handling.
- Testing.

## M7 — Enterprise Use Cases

Cover:

- Enterprise Knowledge Management.
- Customer Support.
- Research Assistance.
- Code Assistance.
- Multimodal RAG.
- Business Intelligence.

## M8 — Interview Preparation

Produce:

- Advanced interview question bank.
- System design scenarios.
- Architecture cheat sheets.
- Flashcards.
- Model answers.
- Mock interviews.
- Quick revision guides.

## M9 — Final Validation and Delivery

Validate the complete handbook and reference implementation.

Generate:

- Complete Markdown handbook.
- PDF handbook.
- Diagrams.
- Reference implementation.
- Interview preparation package.
- Technical quality report.
- Final README.

Do not declare completion while critical deliverables remain missing.

---

# 5. INCREMENTAL CHAPTER AUTHORING PROTOCOL

This protocol is mandatory.

## 5.1 Chapter Batch Size

Author no more than 2–3 chapters in one batch.

For each batch:

### Step 1 — Research

- Research the selected topics.
- Identify foundational papers.
- Review official documentation.
- Review relevant implementations.
- Verify current technology capabilities.
- Collect credible references.

### Step 2 — Chapter Outline

Define:

- Learning objectives.
- Required concepts.
- Internal mechanisms.
- Architecture diagrams.
- Practical examples.
- Implementation examples.
- Trade-offs.
- Failure modes.
- Production considerations.
- Interview questions.

### Step 3 — Author

Write complete chapters.

Do not write placeholder paragraphs.

Do not replace explanations with superficial bullet lists.

### Step 4 — Technical Review

Verify:

- Factual accuracy.
- Architectural correctness.
- Terminology.
- API behavior.
- Code examples.
- Citations.
- Diagram accuracy.
- Consistency with previous chapters.

### Step 5 — Integration

Update:

- Canonical handbook.
- Chapter index.
- Glossary.
- References.
- Progress tracker.
- Open issues.

### Step 6 — Completion Gate

A chapter is complete only when:

- All required sections exist.
- Research is documented.
- Diagrams render.
- Code examples are verified or explicitly marked as illustrative.
- Interview questions exist.
- References exist.
- Quality review is complete.

Only then proceed to the next batch.

## 5.2 Canonical Document Management

The canonical handbook is:

`docs/RAG-Architecture-Handbook.md`

Chapter files are modular authoring artifacts.

Maintain consistent content across both.

Do not allow the master handbook to become outdated relative to completed chapter files.

Use scripts or a deterministic integration process when possible.

Avoid uncontrolled duplication.

---

# 6. RESEARCH AND SOURCE VERIFICATION STANDARDS

## 6.1 Source Hierarchy

Use the following source priority.

### Tier 1 — Authoritative Sources

- Official product documentation.
- Official API references.
- Official engineering blogs.
- Official architecture documentation.
- Original research papers.
- Standards organizations.

### Tier 2 — High-Quality Technical Sources

- Peer-reviewed research.
- Reputable engineering publications.
- Maintained GitHub repositories.
- Verified production engineering case studies.

### Tier 3 — Supplementary Sources

- Community discussions.
- Reddit.
- Stack Overflow.
- Personal technical blogs.

Use Tier 3 sources to discover operational issues and community experiences.

Do not rely on them as the sole source for critical architectural claims.

## 6.2 Source Verification Rules

For every important technical claim:

1. Identify the original source.
2. Verify the claim.
3. Record the source URL.
4. Record the access date.
5. Record publication date when available.
6. Record the relevant technology version.
7. Add a citation to the chapter.

For API usage:

- Verify the API against official documentation.
- Verify the package version.
- Verify method signatures.
- Verify configuration options.
- Verify behavior.
- Verify deprecations.

Never infer that an API exists because a code sample looks plausible.

## 6.3 Source Register

Maintain:

`project-management/RESEARCH-REGISTER.md`

Each entry must contain:

- Source ID.
- Topic.
- Source title.
- URL.
- Source type.
- Publisher.
- Publication date.
- Access date.
- Technology version.
- Claims supported.
- Verification status.
- Relevant chapters.

Use stable source IDs.

## 6.4 Citation Rules

Use numbered references or consistent Markdown citations.

Every chapter must have a References section.

Every significant technical claim must have a supporting source.

Do not cite sources that were not reviewed.

Do not cite search-result snippets as if the original documentation had been verified.

Do not create fabricated references.

For external images, include source URLs and attribution.

## 6.5 Research Freshness

Record the actual research date.

For fast-changing technologies, revalidate information before final delivery.

Pay special attention to:

- Model APIs.
- Embedding models.
- Vector database capabilities.
- Cloud services.
- SDK versions.
- Framework releases.
- Pricing.
- Deployment options.
- Security features.

Clearly identify version-sensitive content.

---

# 7. TECHNICAL WRITING STANDARDS

## 7.1 Required Chapter Structure

Every major chapter must contain:

1. Learning objectives.
2. Problem statement.
3. Why it matters.
4. Core concepts.
5. Internal mechanics.
6. Architecture.
7. Mermaid diagrams.
8. Practical examples.
9. Implementation.
10. Trade-offs.
11. Failure modes.
12. Security considerations.
13. Performance considerations.
14. Cost considerations.
15. Production recommendations.
16. Architecture decision guidance.
17. Interview questions.
18. Exercises.
19. Summary.
20. References.

Adapt this structure when it does not suit the topic, but preserve technical depth.

## 7.2 Explanation Style

Use:

- Clear technical language.
- Intuitive explanations.
- Realistic enterprise examples.
- Tables for comparison.
- Diagrams for complex workflows.
- Code for practical implementation.
- ADRs for decisions.

Explain unfamiliar concepts using analogies to distributed systems when useful.

Avoid:

- Generic motivational language.
- Repetitive content.
- Artificially inflated chapter lengths.
- Unnecessary jargon.
- Unsupported statements.
- Excessive shallow bullet points.

## 7.3 Technical Depth

For every important architecture pattern explain:

- The underlying problem.
- The mechanism.
- The architectural context.
- The operational behavior.
- The trade-offs.
- The failure modes.
- The selection criteria.

The objective is architectural competence, not memorization.

---

# 8. DIAGRAM AND VISUALIZATION STANDARDS

## 8.1 Mandatory Diagram Format

Use Mermaid as the primary diagram format.

Store diagram source files under:

`docs/assets/diagrams/`

Use:

- Flowcharts.
- Sequence diagrams.
- Architecture diagrams.
- C4 diagrams.
- State diagrams.
- Entity relationship diagrams.
- Decision trees.

## 8.2 Diagram Quality

Every diagram must:

- Communicate a specific concept.
- Have clear labels.
- Show relevant components.
- Show directional flows.
- Identify trust boundaries where applicable.
- Be technically accurate.
- Render successfully.

Do not create diagrams that merely decorate a page.

## 8.3 External Images

Use external images only when they provide educational value.

Prefer:

- Official architecture illustrations.
- Original research diagrams.
- Documentation diagrams.
- Verified technical visuals.

For every external image:

- Record the original URL.
- Record the publisher.
- Record attribution.
- Record licensing information when available.
- Ensure the image is accessible or provide a local asset where legally permitted.

Do not reproduce copyrighted images without appropriate permission or licensing.

## 8.4 Custom Diagrams

When external visuals are unavailable, create original Mermaid diagrams.

Do not misrepresent original diagrams as official vendor diagrams.

---

# 9. REFERENCE IMPLEMENTATION GOVERNANCE

## 9.1 Repository Separation

The application must remain under:

`reference-implementation/`

Documentation may reference implementation files.

The handbook must not contain the only copy of critical implementation code.

Maintain a coherent, runnable application.

## 9.2 Technology Selection

Use a production-oriented architecture.

Preferred candidates:

- Python.
- FastAPI.
- Pydantic.
- PostgreSQL.
- pgvector.
- Next.js.
- TypeScript.
- Docker.
- OpenTelemetry.
- GitHub Actions.
- Azure.

Do not blindly use every preferred technology.

Select the architecture based on requirements.

Document decisions in ADRs.

Avoid unnecessary frameworks and abstractions.

## 9.3 Architecture Requirements

The implementation must support:

- Document ingestion.
- Document extraction.
- Chunking.
- Metadata.
- Embeddings.
- Vector indexing.
- Hybrid retrieval.
- Reranking.
- Context assembly.
- Grounded generation.
- Citation validation.
- Authentication.
- Authorization.
- Tenant isolation.
- Document deletion.
- Background processing.
- Evaluation.
- Observability.
- Error handling.
- Deployment.

## 9.4 Implementation Workflow

For every major capability:

1. Review requirements.
2. Review architecture.
3. Identify dependencies.
4. Research APIs.
5. Create or update ADR.
6. Implement.
7. Add tests.
8. Execute tests.
9. Fix failures.
10. Validate integration.
11. Update documentation.
12. Update progress.

Never implement multiple unrelated capabilities without intermediate validation.

## 9.5 Coding Standards

### Python

- Use type hints.
- Use Pydantic schemas.
- Follow PEP 8.
- Use clear module boundaries.
- Use dependency injection where appropriate.
- Use async appropriately.
- Avoid blocking operations in async endpoints.
- Use structured logging.
- Use configuration management.
- Use explicit error handling.
- Avoid unnecessary global state.
- Keep business logic independent of HTTP handlers.

### TypeScript

- Use strict TypeScript.
- Avoid `any` unless justified.
- Use reusable components.
- Separate UI from API logic.
- Handle loading and error states.
- Validate API responses.
- Implement accessibility.
- Avoid duplicated business logic.

### Database

- Use migrations.
- Define appropriate constraints.
- Define indexes based on access patterns.
- Avoid unbounded queries.
- Implement tenant-aware data access.
- Use transactions appropriately.
- Document data lifecycle.
- Define retention and deletion policies.

### Infrastructure

- Use Infrastructure as Code where practical.
- Avoid hardcoded secrets.
- Prefer managed identity.
- Implement health checks.
- Implement resource limits.
- Define scaling policies.
- Document environment configuration.
- Use reproducible deployment practices.

## 9.6 Dependency Management

Pin dependencies.

Maintain lockfiles.

Verify compatibility.

Prefer maintained libraries.

Review licensing.

Avoid unnecessary dependencies.

Document:

- Package purpose.
- Version.
- License.
- Known limitations.
- Security considerations.

---

# 10. SECURITY ENGINEERING STANDARDS

Security is a mandatory architectural concern.

## 10.1 Threat Modeling

Perform threat modeling for:

- Document ingestion.
- Retrieval.
- Generation.
- Tool execution.
- Tenant isolation.
- Authentication.
- Authorization.
- Data storage.
- Logging.
- Deployment.

Use a recognized threat-modeling approach where appropriate.

## 10.2 Mandatory Security Controls

Address:

- Authentication.
- Authorization.
- Tenant isolation.
- Document-level access control.
- Permission-aware retrieval.
- Secrets management.
- Encryption in transit.
- Encryption at rest.
- Input validation.
- Output validation.
- Prompt injection.
- Indirect prompt injection.
- Malicious documents.
- Data exfiltration.
- PII handling.
- Audit logging.
- Rate limiting.
- Abuse prevention.

## 10.3 Security Rules

Never:

- Hardcode secrets.
- Commit credentials.
- Log sensitive prompts or documents unnecessarily.
- Trust retrieved content as instructions.
- Allow cross-tenant retrieval.
- Treat prompt instructions as the only security boundary.
- Give agents unrestricted tool access.
- Claim security guarantees without evidence.

Document limitations and residual risks.

---

# 11. TESTING AND VALIDATION STANDARDS

## 11.1 Testing Strategy

Implement appropriate levels of testing.

### Unit Tests

Test:

- Chunking.
- Metadata extraction.
- Query rewriting.
- Context assembly.
- Citation handling.
- Business logic.
- Validation.

### Integration Tests

Test:

- Database.
- Vector search.
- Embedding integration.
- LLM integration.
- Ingestion pipeline.
- Retrieval pipeline.
- Authentication.
- Tenant isolation.

### Evaluation Tests

Test:

- Retrieval Recall@K.
- Precision.
- MRR.
- NDCG.
- Faithfulness.
- Answer relevance.
- Citation correctness.
- Groundedness.

### Security Tests

Test:

- Unauthorized access.
- Cross-tenant access.
- Permission filtering.
- Prompt injection.
- Data leakage.
- Input validation.

### Performance Tests

Test:

- Ingestion throughput.
- Retrieval latency.
- End-to-end latency.
- Time to first token.
- Concurrent requests.
- Memory utilization.
- Cost per query.

## 11.2 Test Execution Rules

Before declaring an implementation complete:

1. Run the relevant unit tests.
2. Run the relevant integration tests.
3. Run static analysis.
4. Run type checks.
5. Run formatting and linting.
6. Validate migrations.
7. Validate configuration.
8. Validate application startup.
9. Validate relevant API endpoints.
10. Review test output.

Fix failures before moving forward.

If a test cannot be executed:

- Explain why.
- Identify the limitation.
- Do not claim success.
- Record the unresolved issue.

## 11.3 Test Reporting

Maintain:

`project-management/QUALITY-REPORT.md`

Record:

- Test command.
- Date.
- Environment.
- Test count.
- Passed.
- Failed.
- Skipped.
- Known limitations.
- Outstanding defects.

Never fabricate test results.

## 11.4 Production Readiness

A passing test suite does not automatically make the application production-ready.

Review:

- Security.
- Reliability.
- Scalability.
- Observability.
- Cost.
- Deployment.
- Data lifecycle.
- Operational procedures.
- Disaster recovery.

Use explicit readiness criteria.

---

# 12. RAG EVALUATION STANDARDS

Separate retrieval evaluation from generation evaluation.

## Retrieval Evaluation

Measure:

- Recall@K.
- Precision@K.
- Hit Rate.
- MRR.
- NDCG.
- Retrieval latency.
- Candidate diversity.

## Generation Evaluation

Measure:

- Faithfulness.
- Answer relevance.
- Correctness.
- Citation accuracy.
- Context utilization.
- Hallucination rate.

## System Evaluation

Measure:

- End-to-end latency.
- Time to first token.
- Cost per query.
- Success rate.
- Error rate.
- User satisfaction.
- Security violations.

Maintain a versioned golden dataset.

Every meaningful change to:

- Chunking.
- Embeddings.
- Retrieval.
- Reranking.
- Prompt templates.
- Models.
- Context assembly.

must trigger appropriate regression evaluation.

Do not optimize a single metric while ignoring the overall system.

---

# 13. PERFORMANCE AND COST ENGINEERING

Every major design must consider:

- Latency.
- Throughput.
- Concurrency.
- Resource consumption.
- Model costs.
- Embedding costs.
- Vector storage costs.
- Reranking costs.
- Data ingestion costs.
- Operational costs.

Provide explicit cost models when sufficient pricing information exists.

Clearly label assumptions.

Do not fabricate production benchmarks.

Use benchmark methodology and reproducible tests.

Distinguish:

- Measured performance.
- Estimated performance.
- Theoretical performance.
- Illustrative performance.

---

# 14. ARCHITECTURE DECISION RECORDS

Create an ADR for every significant architecture decision.

Use the following format.

```markdown
# ADR-XXX: Decision Title

## Status

Proposed | Accepted | Superseded | Deprecated

## Context

What problem must be solved?

## Requirements

Functional and non-functional requirements.

## Options Considered

Option A
Option B
Option C

## Decision

Selected approach.

## Rationale

Why was it selected?

## Trade-offs

What advantages and disadvantages are accepted?

## Consequences

Impact on implementation and operations.

## Security Considerations

Relevant security implications.

## Performance and Cost

Expected impact.

## Reversal Conditions

When should the decision be reconsidered?

## References

Verified sources.
```

Do not make major architecture decisions without documenting the rationale.

---

# 15. PROGRESS TRACKING AND SESSION CONTINUITY

Progress tracking is mandatory.

Claude Code must maintain:

`project-management/PROGRESS.md`

## 15.1 Progress File Structure

```markdown
# Project Progress

## Current Milestone

M0 - Project Initialization

## Current Batch

Not started

## Completed Chapters

- [ ]

## Chapters In Progress

- [ ]

## Pending Chapters

- [ ]

## Completed Implementation Components

- [ ]

## In Progress Implementation Components

- [ ]

## Pending Implementation Components

- [ ]

## Completed Deliverables

- [ ]

## Current Blockers

- [ ]

## Known Technical Issues

- [ ]

## Research Pending

- [ ]

## Tests Executed

- [ ]

## Last Completed Task

Description

## Next Exact Action

Description

## Last Updated

YYYY-MM-DD
```

## 15.2 Update Progress After Every Batch

After each completed batch:

- Update chapter completion.
- Update implementation completion.
- Update test status.
- Update research status.
- Record unresolved issues.
- Record the next exact action.

Do not rely on conversational memory.

The progress file is the source of truth.

## 15.3 Session Startup Protocol

At the beginning of every new Claude Code session:

1. Read `CLAUDE.md`.
2. Read `project-management/PROGRESS.md`.
3. Read `project-management/MASTER-TOC.md`.
4. Read `project-management/EXECUTION-PLAN.md`.
5. Read relevant ADRs.
6. Inspect relevant files.
7. Check Git status.
8. Identify the last completed milestone.
9. Identify the next exact action.

Resume from the last verified checkpoint.

Do not restart completed work.

Do not overwrite validated deliverables without justification.

## 15.4 Session Ending Protocol

Before ending a work session:

1. Complete the current bounded task.
2. Run relevant validations.
3. Update progress.
4. Record unresolved issues.
5. Record next steps.
6. Identify modified files.
7. Summarize the completed work.

Never leave progress tracking outdated.

---

# 16. GIT AND CHANGE MANAGEMENT

Use Git for change management.

Before significant modifications:

- Inspect current Git status.
- Review relevant files.
- Preserve existing work.
- Avoid destructive changes.

Use meaningful commits when requested or when appropriate.

Suggested commit conventions:

- `docs: add RAG fundamentals chapters`
- `research: verify embedding model capabilities`
- `feat: implement document ingestion pipeline`
- `feat: add hybrid retrieval`
- `test: add tenant isolation tests`
- `fix: correct citation validation`
- `infra: add container deployment`

Do not:

- Force-push without explicit authorization.
- Delete user work.
- Commit secrets.
- Ignore failing tests.
- Hide implementation defects.

---

# 17. FINAL DELIVERABLE REQUIREMENTS

The project must ultimately produce the following.

## 17.1 Master Handbook

`docs/RAG-Architecture-Handbook.md`

The handbook must contain the complete integrated technical reference.

## 17.2 Supporting Documentation

- Executive overview.
- Fundamentals.
- Architecture.
- Advanced RAG.
- Production implementation.
- Security and governance.
- Evaluation and LLMOps.
- Interview guide.
- Question bank.
- ADR catalog.
- Production readiness checklist.
- Glossary.
- References.

## 17.3 Reference Implementation

A coherent application under:

`reference-implementation/`

It must include:

- Backend.
- Frontend.
- Database.
- Migrations.
- Tests.
- Evaluation.
- Observability.
- Infrastructure.
- Deployment.
- README.
- Configuration templates.

## 17.4 Visual Deliverables

- Architecture diagrams.
- Sequence diagrams.
- Decision trees.
- Retrieval workflows.
- Security diagrams.
- Deployment diagrams.

## 17.5 Interview Preparation

Include:

- 100+ advanced interview questions.
- 15–25 system design scenarios.
- Model answers.
- Trade-off explanations.
- Quick revision guides.
- Architecture cheat sheets.
- Flashcards.
- Mock interview exercises.

## 17.6 PDF

Generate:

`output/RAG-Architecture-Handbook.pdf`

Requirements:

- Professional layout.
- Clickable table of contents.
- Readable code blocks.
- Rendered diagrams.
- Consistent typography.
- Page numbering.
- References.
- No broken images.
- No truncated content.

If PDF generation is unavailable, document the limitation and provide the complete Markdown source.

---

# 18. FINAL QUALITY GATES

The project cannot be marked complete until the following are verified.

## Documentation

- All required chapters exist.
- The handbook is integrated.
- Citations are verified.
- References are complete.
- Diagrams render.
- Terminology is consistent.
- No critical placeholders remain.
- Interview content is complete.

## Implementation

- Application structure exists.
- Backend starts.
- Frontend starts.
- Database migrations work.
- Ingestion works.
- Retrieval works.
- Generation works.
- Citations work.
- Tenant isolation is tested.
- Authentication and authorization work.
- Observability exists.
- Tests have been executed.

## Engineering

- No hardcoded secrets.
- No fabricated benchmark results.
- No unverified API claims.
- No critical unresolved security defects.
- No undocumented architecture decisions.
- No false claims of production readiness.

## Final Report

Create:

`project-management/FINAL-DELIVERY-REPORT.md`

Include:

- Project scope.
- Completed milestones.
- Completed chapters.
- Completed implementation features.
- Technology versions.
- Research date.
- Tests executed.
- Test results.
- Performance results where measured.
- Known limitations.
- Outstanding issues.
- Final artifact locations.
- Production readiness assessment.

---

# 19. DEFINITION OF DONE

A task is DONE only when:

1. The requested artifact exists.
2. It meets the specified requirements.
3. Technical claims are verified.
4. Relevant tests are executed.
5. Failures are resolved or documented.
6. Documentation is updated.
7. Progress is updated.
8. The next step is clear.

A chapter is not complete merely because text has been generated.

An application feature is not complete merely because code has been written.

A production implementation is not complete merely because it compiles.

A project is not complete merely because its files exist.

---

# 20. EXECUTION INSTRUCTIONS

Start by inspecting the repository.

If the repository is empty:

- Initialize the required structure.
- Create the project management files.
- Define the master table of contents.
- Create the execution plan.
- Establish the research register.
- Establish the progress tracker.

If the repository already contains work:

- Inspect it.
- Preserve it.
- Identify completed milestones.
- Resume from the current checkpoint.

Then execute the project systematically.

Do not generate the entire handbook in one pass.

Do not stop after creating the table of contents.

Do not stop after the first few chapters.

Do not claim completion prematurely.

Use the available tools to research, implement, validate, and generate deliverables.

Prioritize technical accuracy over speed.

Prioritize architecture depth over superficial breadth.

Prioritize working code over illustrative claims.

Prioritize reproducibility over assumptions.

**The objective is to create a technically authoritative, production-oriented RAG Architecture Handbook and a coherent reference implementation that an experienced Enterprise Solution Architect can use for real-world engineering, architecture reviews, and advanced interviews.**

Begin with M0 — Project Initialization.

Read this file and establish the initial project state before proceeding.