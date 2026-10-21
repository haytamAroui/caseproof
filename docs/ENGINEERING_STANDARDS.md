# CaseProof Engineering Standards

## Architecture
- Hexagonal, DDD-informed modular monolith. Domain objects and rules are framework-independent. Modules communicate through declared application interfaces, not table shortcuts.
- Suggested modules: tenancy, intake, documents, evidence, reconciliation, finance, rules, workflow, reviews, dossiers, audit.
- HTTP routes perform authentication, typed request parsing and orchestration; business logic lives in domain/application services. No circular imports. Reject changes violating import boundaries.

## Python
- Supported pinned Python version documented in pyproject. Format/lint with Ruff, typecheck with Pyright/mypy, pytest and coverage gates. Lock dependencies and track CVEs.
- Explicit type annotations; Pydantic schemas at I/O; frozen dataclasses/value objects for domain entities. Avoid Any, unchecked casts, magic globals and broad except.
- Async only for real I/O; use timeouts, cancellation, bounded concurrency. Do not mix sync DB calls into async routes.
- Money: Decimal, explicit currency, exact rounding and source basis. Dates: timezone-aware instants with documented legal local-time interpretation. Never float.
- Structured exceptions and problem-details responses. No silent recovery, fabricated default values or unvalidated LLM JSON.

## TypeScript and UI
- TypeScript strict and linted. Server-side authorization on all mutations. Accessible keyboard and screen-reader interfaces (WCAG 2.2 AA goal). Ingestion flow, evidence grid, source citation viewer, exception queue, dossier preview.
- Generated API clients from OpenAPI or shared contracts. No handwritten duplicate DTOs, speculative abstraction, decorative dashboards or irreversible actions without clear review.

## Postgres
- Dedicated Supabase project, RLS everywhere exposed, application-level authorization when using privileged credentials. Prefer private schemas. Versioned migrations; never alter applied migrations. Composite tenant-scoped FK when appropriate. Validate SECDEF grant/search_path.
- Source bytes immutable and content-addressed. Store object key, not public URL. Audit events append-only. Durable jobs with transactionally committed state, lease and retry idempotency.

## LLM and evidence
- LLM outputs are proposals, never authoritative calculations or legal verdicts. Record provider/model/schema/prompt versions, costs and input hashes with privacy controls.
- Machine-verified quotation does not establish underlying factual truth. Maintain independent citation, corroboration, contradiction and legal review states.
- No general-purpose agents, vector DB or RAG until a benchmark justifies it.

## Testing
- Unit, property-based financial/rule tests, parser golden corpus, integration auth tests, adversarial prompt-injection tests, PDF snapshots, worker crash/restart recovery, API contract tests, E2E critical paths.
- Before merging: tests, static checks, migration checks, security review, no regressions in verified evidence trace and tenant boundaries.

## Git and agent execution
- One bounded task per branch and PR. Small diffs, conventional commits, checklist and test evidence. Never push secrets or real customer documents.
- Agents must inspect repository state, read CONSTITUTION, state assumptions, plan changes, implement tests first for safety-sensitive logic, run checks, review diff and report exact results. No unsubstantiated DONE claims.

## Stage 1 normative trust contracts
1. **Finding:** Candidate findings may be ungrounded only in quarantine. Promotion requires typed evidence anchors tied to immutable source versions. Citation resolution, content fidelity, semantic support and sufficiency are independent statuses. A quote matching source text is not proof that a finding is true. Model confidence is metadata, never approval authority. Pydantic validates I/O; domain models remain framework-independent.
2. **Coverage:** Record scoped questions, document/version inventory, processed/failed/excluded status, reviewer-authorized exclusions, missing evidence, contradictions and completion policy. `PROCESSED` is not sufficient for completion. A JSONB snapshot may be a projection, not the sole authoritative audit history.
3. **Promotion:** An approved conclusion requires prescribed evidence checks and authorized human decision. Contradicted or insufficient evidence remains visibly so even when an authorized, policy-permitted exception disposition is recorded. Missing authority returns forbidden; invalid transitions return structured conflicts.
4. **Atomic provenance:** Production state transitions and corresponding audit events commit atomically with idempotency and recovery tests. Stage 1 in-memory ledger is not durable, tamper-proof or sufficient for production.
5. **Evaluation:** Deterministic invariant tests are merge gates, not guarantees of factual truth. Keep kernel fixtures distinct from finance reconciliation and later agent benchmarks. Test wrong passage, wrong version, genuine quote with false claim, contradiction, omission, cross-tenant access and unauthorized overrides.

Reference ADRs: `docs/adr/0008-evidence-anchors.md` and `docs/adr/0009-coverage-promotion.md`. Breaking HTTP changes require a new versioned contract; do not silently rewrite `contracts/kernel-api.v1.json`.

## Stage 1 contract implementation handoff
- `docs/adr/0008-evidence-anchors.md` specifies source-version/representation identity and typed locator coordinate bases; never silently remap anchors after OCR/parser changes.
- `docs/adr/0009-coverage-promotion.md` defines issue-to-source closure policy, conflict aggregation, optimistic revision/idempotency semantics and a separate BUSINESS_EXCEPTION_ACCEPTED operational disposition.
- `contracts/kernel-api.v2.proposal.json` is an **informative design outline**, not runnable OpenAPI/JSON Schema. KRN-109 must add implementable schemas, examples, validators and negative contract tests before exposing v2.
- Treat JSON contract drafts as contract/configuration artifacts for C25 verification. The Markdown-only documentation commit exception does **not** exempt PR #8 from required CI and merge protection. Missing runner/failed workflow is a blocker, not a failed architecture test result. Human sign-off and independent review remain mandatory.
