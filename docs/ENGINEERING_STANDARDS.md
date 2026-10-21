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

## Stage 1 normative trust contracts (pending ADR approval)
1. **Finding contract.** An evidence-backed finding refers to immutable document versions through typed, resolvable anchors. Ungrounded candidates may be retained only in a non-promotable state. Integrity, citation resolution, quote/value fidelity, semantic support and sufficiency are independently represented. Optional model confidence is never proof. Domain value objects are pure Python; Pydantic belongs at I/O.
2. **Coverage contract.** Version the investigation scope, required issues and expected inputs. Record processing attempts, exclusions, unresolved questions, contradiction and explicit waivers. Completion depends on policy satisfaction, not a mere PROCESSED marker. A JSONB manifest may be a projection, not the sole audit source.
3. **Promotion gate.** Authorized reviewers may approve supported conclusions or explicitly authorized exception dispositions. Exception rationale and policy must be audited. Contradicted/insufficient evidence stays labeled as such; no override may silently convert it to verified. Reject invalid transitions and unauthorized actors separately.
4. **Provenance.** Stage 1 defines immutable events and ports; Stage 2 must atomically persist domain changes and audit events, with idempotency, tenant isolation and crash recovery. Hash chains without external anchoring are not tamper-proof.
5. **Evaluation.** Separate deterministic kernel tests, finance reconciliation golden fixtures and agent harness benchmarks. Use known versioned ground truth, negative controls and private holdouts. Do not claim that tests mathematically guarantee truth.

Reference: proposed ADRs 0008, 0009, 0010 and `contracts/kernel-api.v2.proposal.json`. These are not yet implemented API routes or an approved schema migration.
