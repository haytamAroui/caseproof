# ADR 0010 — CaseProof-native Stage 2 durability and trust boundaries

**Status:** Proposed for independent architecture/security review; not approved implementation or deployed behavior.
**Date:** 2026-10-22
**Scope:** ExceptionDesk finance-first application, using the sector-neutral CaseProof Evidence Kernel.
**Authority:** `CONSTITUTION.md`, `docs/ROADMAP.md`, `docs/standards/database-v1.md`, ADRs 0001, 0004, 0007, 0008 and 0009. Existing merged Stage 2 source code and installed migration remain authoritative for their actual behavior.

## Context and product intent

ExceptionDesk initially resolves **supplier invoice versus purchase order exceptions** for Belgian finance operations teams. CaseProof factual dispute dossiers are a later consumer of the same evidence and review history. The customer's outcome is a traceable, reviewable exception decision, **not** autonomous legal judgment or a generic AI chatbot.

KRN-101–109 implement a tested, **in-memory** evidence reference: immutable original-source and derived-representation identity, typed anchors, quote/value fidelity, proposed semantic relations, source/issue coverage, policy-based grounding eligibility, provenance and strict proposed v2 I/O contracts. A citation match does not establish truth; model-supplied labels and claimed human identities do not confer authority.

Stage 2 currently includes a **development** Supabase/PostgreSQL foundation of seven tables, RLS negative tests, a standalone Auth verification adapter, and a not-yet-live read-only case-membership adapter. The full evidence graph, original bytes, review transactions, authenticated real-tenant integration, durable worker and live v2 routes do not yet exist. S2-006's manual genuine Auth probe still requires separate test-account/environment setup; normal green CI is not evidence of real signed sessions.

## Decision: reuse engineering lessons, design independent CaseProof code

Borrow **failure modes and invariants**, not runtime coupling, database migrations, unreviewed helper functions, role mappings, provider defaults, domain schemas or implementation source code from AZComply. Its separate database and deployment remain untouched.

Transferable lessons:
1. A source artifact needs a stable digest, private storage key, lifecycle state and verified relation to an exact representation.
2. A human decision and its audit, idempotency receipt and derived projection must agree after *every* failure, not just on successful requests.
3. A durable worker must persist intent, checkpoints and external-call outcomes. Uncertain remote execution is **OUTCOME_UNKNOWN**, not proof of failure or permission for blind replay.
4. Field extraction candidates need explicit source locations and field-level validator outcomes. A confidence score is not evidence authority.
5. Recomputed user-facing status is a projection from authoritative immutable records and explicit versioned policy, not an independently editable truth flag.

No AZComply modules, tables, secrets, prompts or internal details are incorporated by this ADR. No shared runtime, package or network integration is authorized.

## Architecture and ownership

```text
web/mobile client (future)
         |
   FastAPI HTTP adapter: parse + authenticate; no domain decisions
         |
   Application use cases / trusted composition root
   ├─ Authorization: verified IdP identity + current membership
   ├─ Evidence: immutable source/version/representation repository
   ├─ Policies: frozen scope + current, versioned rule/coverage
   ├─ Review: authorize + recheck + atomic transition/audit/idempotency
   └─ Worker: persisted jobs/leases/checkpoints/outbox
         |
   Pure sector-neutral packages/evidence_kernel (KRN-101–109)
         |
   Domains/finance (first)      Domains/disputes (later)
         |
   Infrastructure ports implemented by Postgres and private object storage
```

**Dependency direction:** HTTP, workers and concrete adapters depend inward; neither kernel nor domains import database, FastAPI, Supabase, provider SDKs or each other. Follow the existing modular monolith and one durable worker decision. Do not build agent orchestration into Stage 2.

**Owned sources of truth:**
- PostgreSQL: org membership, case state, source/representation metadata, finding and link revisions, frozen coverage/policy references, review decisions, append-only audit, idempotency receipts and job coordination.
- Private object storage: **captured source bytes** and parser outputs, referenced by immutable object identity and SHA-256; object URLs are never identifiers or authorization grants.
- Kernel: sector-neutral **rules and types** for resolving and evaluating evidence; does not own SQL transactions.
- Finance domain: Decimal, currency, like-for-like comparison, tolerances and exception semantics; no legal or sector-specific logic in kernel.
- Human-review application: authorization, effective policy selection, action-specific signoff and business exception disposition distinct from approval.

## Persist the kernel graph rather than flattening it

The seven-table schema is a foundation, **not** a complete representation of KRN-101–109. The following are proposed logical records, not executable schema:

| Record | Required durable contract |
|---|---|
| `source_versions` (extends existing document versions) | tenant, case, original byte digest, immutable object reference, capture time, media/size and access policy |
| `representations` | tenant, parent source-version/digest, own immutable byte digest, parser/OCR implementation+version, configuration hash, coordinate convention and trusted layout manifest |
| `finding_revisions` | tenant/case, immutable statement text or private content reference, exact revision/hash, author provenance, no in-place rewriting |
| `evidence_link_revisions` | exact finding revision, typed anchor including source/representation identity, deterministic resolution and fidelity, separate semantic/sufficiency *proposal* and assessment revision |
| `coverage_manifest_revisions` | case, scope/policy revisions, required issues and source inventory, omissions/exclusions and declared link selectors |
| `review_decisions` | trusted action-scoped human actor, frozen finding/link/coverage/policy versions, reason, disposition, attestation and immutable audit reference |
| `audit_events` | event schema version, trusted tenant/actor, previous/next state, correlation/causation, input fingerprint, safe metadata; no UPDATE/DELETE grants |
| `idempotency_records` | operation scope+key, exact semantic fingerprint, committed result reference and event/decision pointer |

Every tenant-owned relationship must use server-derived organization ownership and appropriate composite FKs. Parser representations are append-only and must not silently remap old offsets or anchors. Store raw content privately; audit/event payloads use minimized references and digests, not private quotes or credentials. Source/version IDs and original bytes are distinct from extracted assertions.

**The storage/review graph requires its own independently reviewed additive migration and rollback/recovery plan; do not modify the existing installed migration or apply this table list as SQL.**

## Trusted identity and data-access strategy: an explicit security gate

Supabase Auth verifies real user identity; server-controlled organization membership and **current** action permissions establish authorization. Neither a client tenant header, editable JWT metadata nor a PostgreSQL `SET` setting is authority. A genuine signed session is still not a verified human *reviewer*; until reviewer assurance exists, `human_authenticated=False` must block `approved_conclusion`.

The existing private schema uses RLS and very narrow authenticated SELECT grants. It is not exposed through the Supabase Data API. The first production application composition must choose and **prove** one of:
- **User-scoped execution** under verified Supabase request identity with independently tested database-level policies where accessible; or
- **Dedicated least-privilege server-side connection** with explicit command-level ownership and active-membership validation in the same transaction, an independently reviewed database privilege strategy and no broad `service_role` bypass.

These are alternatives requiring a specific, reviewed connectivity design—not permission to combine an untrusted user-supplied actor ID with a privileged connection. `SECURITY DEFINER` is exceptional and requires explicit security review of execution grants, `search_path`, role ownership and spoofed-actor tests. Runtime connection pooling must not leak one user's authorization context into another.

Before any v2 exposure, run **real signed Auth session -> application -> real PostgreSQL runtime role** tests across two organizations, including membership revocation, cross-tenant joins and source/download protection. Disposable simulated `auth.uid()` tests are useful but not sufficient.

## Atomic decision boundary (S2-004)

A consequential transition has one database transaction, or no acknowledged result:

1. Validate/verify identity at the server entry and derive tenant/case permission context; parse a strict, versioned request. Never deserialize trusted principal/tenant from client JSON.
2. Begin transaction. Lock and re-read **current active membership, exact case, effective policy and relevant immutable evidence/coverage revisions** using one documented lock order. Authorization derived before the transaction cannot authorize the write alone.
3. Check unique operation-scoped idempotency key and canonical semantic-input fingerprint **while currently authorized**. Same key+fingerprint returns the previously committed reference only without exposing data after revoked access; same key+different fingerprint conflicts.
4. Re-evaluate exact KRN-105/106/109 preconditions on the authoritative frozen snapshot. Reject missing evidence, forged assessors, stale snapshot, policy/version drift, self-approval and insufficient human attestation. The synthetic Stage 1 preflight is not authorization.
5. Compare-and-swap the expected case revision; insert append-only decision/audit events and the idempotency result/reference in the **same transaction**.
6. Commit before acknowledging. An audit insert failure, version conflict, auth change, cancellation or connection failure rolls back all proposed mutation. Unknown commit acknowledgment requires outcome reconciliation by idempotency lookup before any retry.

**Initial S2-004 may implement an internal fail-closed transaction port against the existing case/audit/idempotency foundation in disposable PostgreSQL. It MUST NOT claim a valid evidence-based promotion or expose a write route until the persistent kernel graph, effective-policy loader and human authorization are independently proved.**

The idempotency fingerprint must include operation, trusted actor/tenant scope, exact semantic payload and preconditions; do not use Python repr, loose JSON serialization or raw tokens. Define replay response structure and versioning before implementation.

## Private storage boundary is not a PostgreSQL transaction

Uploading a blob and committing Postgres metadata cannot be atomic across systems. Use a recoverable protocol:

1. Authenticate and authorize tenant/case, enforce strict size/type, sandbox validation and rate limits; create bounded quarantine intent with a unique immutable object key.
2. Write immutable bytes in a private bucket; read back or otherwise verify stored content digest and byte count before making it referenceable.
3. Transactionally publish the *verified* metadata and source-version record, preserving the original object version and hash. Parser/OCR outputs create separate representations with lineage.
4. On interruption, reconciliation workers inspect pending/failed/orphan states; no silent overwrite, premature availability, cross-tenant key reassignment or deletion of referenced approved evidence.
5. Enforce server-side access on every signed-URL issuance; short TTL, scope checks, retention/legal hold and lawful erasure policy precede customer uploads.

This differs deliberately from any best-effort upload followed by a separate metadata update that could leave a falsely available source.

## Durable runtime and external side effects

Start with deterministic finance and document-processing jobs. A persisted step identity and input/release fingerprint decide whether a resumed step reuses its prior result. Work claims use transactional lease, heartbeat, expiry, attempts and bounded retry policy; completion includes durable event/outbox consistency. Workers must re-establish server-owned tenant rights on every state-changing operation.

An external provider call has distinct `CREATED` -> `DISPATCH_INTENT_RECORDED` -> `RESPONSE_CAPTURED` -> `SUCCEEDED` / `FAILED_BEFORE_DISPATCH` / `OUTCOME_UNKNOWN` states. A timeout **after dispatch** is not evidence the provider did not execute; replay only when provider-native idempotency or reconciliation proves safety. Save response bytes privately before schema interpretation; record provider, model, prompt/schema versions and limited diagnostics without logging document content.

Outbox delivery is at least once. Consumers deduplicate on stable event identity; no external emails, legal filings, payments or demands run autonomously.

## v2 contract and permission alignment before live activation

`contracts/v2_operation_matrix.json` currently proposes `evidence:write`, `finding:promote`, `conclusion:approve` and `exception:accept`, while `apps/api/access_control.py` and the deployed schema currently know a narrower set (e.g. `finding:write`, `conclusion:request_approval`, `exception:request`). These are **not synonyms**. Do not silently grant broader rights or expose a route with an unmapped permission.

Review and version a complete *request vs decision* action catalog, DB membership constraints, denied unknown actions, separation-of-duties policies and backward compatibility. The actual v2 routes remain disabled until the deployment gate passes. Keep the caller-controlled v1 `X-Tenant-Id` dev interface off untrusted networks and out of any customer release.

## Stage 2 slice plan (proposed; not existing completion claims)

- **S2-004 — Atomic state+audit+idempotency internal command boundary.** Define first; disposable-DB implementation/test next, no public write route or approval until required trusted evidence/identity exists.
- **S2-007 — Real signed-Auth and two-tenant PostgreSQL integration.** Configure two genuine dev users and memberships through an approved path, pin runtime DB privilege model, exercise read isolation and revocation.
- **S2-008 — Durable KRN evidence graph.** New reviewed versioned schema and repository ports for source representations, finding/link revisions, coverage and provenance.
- **S2-009 — Private Evidence Vault.** Quarantine, immutable storage, verified read-back, source/representation hashes, object ACL/URL validation and recovery.
- **S2-010 — Durable worker and crash recovery.** Leases, checkpoints, retries/outbox, idempotent step results and injected failures. Delay optional agent orchestration to Stage 4.

These labels are **new planning proposals**, not a renaming or completion claim for existing S2-005/S2-006. The implementation order may interleave S2-007/008/009 before enabling any S2-004 live command. Stage 3 builds the actual invoice/PO user journey once Stage 2 release gates pass.

## Acceptance / negative-proof matrix

| Risk | Required proof before customer release |
|---|---|
| Tenant crossover | Real signed users A/B cannot read/write each other's case, metadata, source objects, URL, worker job or cached result |
| Revoked member | Recheck active membership at command time; no unauthorized replay of earlier idempotency response |
| Forged authority | Fake human flag, actor ID, tenant ID, role claims and unreviewed policies never authorize review or approval |
| Audit failure | Inject failed audit insert: state, decision and receipt all roll back |
| Concurrent decisions | Two writers at same revision produce one committed decision; other receives deterministic conflict |
| Idempotency | Identical retry returns same authorized committed reference; different fingerprint conflicts, no duplicate events |
| Evidence drift | Hash, parser representation, offset and finding revision changes make old anchors stale or require new reassessment |
| Incomplete coverage | Missing/failed/excluded/contradicting required source or issue blocks ordinary approval; qualified exceptions stay visibly unresolved |
| Object-store interruption | Pending upload not visible as verified; orphan/quarantine recovery, read-back mismatch and signed-URL denial tested |
| Worker crash | Retry/restart never duplicates review, export, charging or external calls with outcome unknown |
| Reviewer UI | Side-by-side exact evidence version, visible contradictions, missing source, authority and action consequences; WCAG 2.2 AA target |

## Non-goals and open decisions

No new production data, migrations, auth accounts, provider integrations, customer outreach, external actions or source copying. No distributed microservices, graph DB, general agent framework or universal legal engine.

Open for review: (1) exact runtime DB role/connection strategy, (2) attestation/MFA/separation-of-duties policy, (3) artifact retention/erasure/legal-hold lifecycle, (4) canonical fingerprint serialization/version, (5) real-source parser layout trust and coordinate mapping, (6) v2 action catalog and transition authority, (7) whether scope/coverage projection is recomputed in SQL or from immutable application snapshots with transactional fingerprint checks. Each requires an ADR or reviewed bounded task before implementation, not guesses.

**Approval gate:** Proposed ADR only. Independent security/architecture review, owner approval for auth/RLS/migration and real cloud-runner evidence for implementation remain mandatory under Constitution C13/C16/C25.
