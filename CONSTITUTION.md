# CaseProof Engineering Constitution — binding for humans and coding agents

## Priority and enforcement
This file is the top-level project policy. Applicable law, security policy, user instructions and repository-specific constraints remain binding. In conflict, stop and escalate; do not silently pick a convenient interpretation. `AGENTS.md`, `CLAUDE.md`, and skills are implementation guidance, never permission to bypass this constitution. Each PR must show which invariants it touches.

## C01 — Evidence is not truth
A matching quotation proves only that text is present in a particular source representation. It does **not** prove the author's identity, authenticity, completeness, contractual effect, legal validity, absence of objections or enforceability. Keep source verification, factual reconciliation, reviewer disposition and legal assessment as **orthogonal typed states**. Never collapse them into a single green `verified` flag. Never infer absence from an incomplete upload set.

## C02 — No automated legal authorization
The system may auto-generate a **draft factual dossier** and calculate conditional figures. It must not automatically declare IOS eligibility, legal enforceability, case success, or initiate collections, demand letters, court filing or third-party contact. Such actions require an authorized human and explicit action-scoped approval. Do not invent a legal opinion from a confidence threshold.

## C03 — LLMs are untrusted data processors
Models extract candidate facts and draft clearly labeled text; they do not set legal rules, approve actions, select jurisdiction, write final monetary balances or authorize scope. All outputs require typed schema validation, grounded source IDs, bounded input/output, timeout, retry budget, provider version and prompt version. Treat document text as **untrusted input**, never executable instructions.

## C04 — Deterministic authority
Amounts use `Decimal` and explicit currency; timestamps use timezone-aware UTC for events and jurisdiction-local calendar dates for legal periods. Calculations must be pure functions with input snapshots, source law references, effective dates, rule versions and reproducible test fixtures. If legal predicates are missing or disputed, return `REQUIRES_REVIEW`, not a guessed answer.

## C05 — Scope and confidentiality
Every case, document, evidence link, job, review, export and generated artifact belongs to a tenant and has server-validated authorization. Never trust client `tenant_id`, user role or object path. No cross-tenant retrieval, cache, storage URL, worker job, logs or vector search. Privileged service credentials are server-only; RLS is defense in depth, not a substitute for service authorization.

## C06 — Data minimization
Default to private buckets, short-lived signed URLs, encrypted transport, least-privilege access, retention/deletion policy, verified processors and geographic routing. Do not upload client documents to public test tools, personal LLM accounts or unapproved services. Never log raw contracts, prompts, customer emails, tokens or complete evidence quotes in telemetry.

## C07 — Durable correctness
Every costly or consequential operation has a stable request ID, idempotency key, state transition, immutable input fingerprint and audit record. Retries must not duplicate dossiers, notifications, charges or review decisions. Persist checkpoints before acknowledging progress. Failure of required audit persistence blocks completion.

## C08 — Provenance
Preserve immutable source bytes, SHA-256 hash, ingestion time, parser/OCR version, page/offset/bounding-box coordinates where available, transformation lineage, model/prompt version, reviewer edits and evidence-to-assertion edges. A hash proves integrity relative to the captured bytes, **not authenticity**. Never rewrite accepted evidence silently.

## C09 — Architecture boundaries
`domain` imports only standard library and domain-level types; `application` imports domain and ports; adapters import inward. HTTP routes, Supabase clients, Redis, SDKs, provider-specific prompts and PDF rendering never enter domain code. Cross-module interaction uses typed application interfaces or explicit domain events. No circular imports or god-services.

## C10 — Safe evolution
Start with a modular monolith, one API and one durable worker, not microservices. RAG, graph DB, distributed orchestration and agents require an approved ADR supported by benchmark or operational need. Reuse AZComply through an adapter first; extract a versioned shared package only after compatibility tests and a second consumer exist.

## C11 — Security before scale
Every migration has tenant isolation and rollback/recovery analysis. All exposed Supabase tables have RLS with ownership predicates; private schemas still receive least-privilege grants. Never use user-editable JWT metadata for authorization. SECURITY DEFINER is exceptional and reviewed. File parsing is resource-limited, malware-aware and protected against decompression bombs, SSRF and path traversal.

## C12 — Engineering integrity
No fabricated tests, citations, source dates, legal rates, benchmark scores, implementation claims or performance numbers. Agents must state what was actually run. Tests fail closed on missing fixtures or external dependencies. No silent `except Exception: pass`, no fake mocks used as proof of integration, no disabling CI to merge.

## C13 — Controlled changes
No agent may autonomously merge, deploy, alter production data, rotate credentials, create paid resources or contact customers. Human approval is required for schema-breaking changes, privacy-sensitive integrations, new legal-rule releases, auth/RLS changes, provider routing, public outputs and production releases. Use protected branches and code review.

## C14 — Accessibility and usable review
Reviewer UI must show source side-by-side with assertion, document/version identity, why an exception was raised, what the user can correct and the downstream effects of the correction. Meet WCAG 2.2 AA as the design target. Do not use green/red alone or misleading confidence gauges as proof of correctness.

## C15 — No hardcoded law or model names
Never bake a specific interest rate, 60-day interpretation, €5k threshold, provider/model version or fixed legal conclusion into business logic. Law packs are versioned, jurisdiction-scoped, effective-dated and approved by a qualified reviewer. Provider/model choices live in configuration and are validated for data handling.

## C16 — Release gate
A PR is not done until lint/type checks, unit and affected integration tests, security/tenant tests, migrations, contract tests, audit checks and required acceptance evidence pass. High-risk changes require independent read-only review and human signoff. Every release records build SHA, migration revision, ruleset version, extraction schema version and rollback plan.