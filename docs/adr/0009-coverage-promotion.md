# ADR 0009 — Coverage ledger, promotion gate and provenance

Status: Proposed — human review required
Date: 2026-10-21

## Decision: issue-based coverage

An investigation declares immutable revisions of its scope and a versioned workflow policy. Its coverage manifest must contain:

- `case_id`, `scope_version`, `manifest_revision`, effective `policy_version`, and required issue IDs with acceptance criteria.
- A versioned expected-source inventory. For each expected document/version, record known, missing, pending, processed, failed, or explicitly excluded status, processing attempt and representation identities, and source-to-required-issue associations. Unknown expected sources are recorded as gaps, not silently dropped.
- Issue-by-issue results: evidence links consulted, required-source constraints, `open`/`supported`/`qualified`/`contradicted`/`unresolved`/`excluded` disposition, recorded gaps and contradictory links, plus the policy decision and immutable rationale. An issue is not closed by processing a document alone.
- Exclusions with reason, scope, affected issue/source, authorizing reviewer, policy permission and audit event. Exclusions never rewrite underlying evidence or conceal unresolved issues.

**Ordinary completion** requires every required issue to meet its versioned acceptance criteria and every expected source to be accounted for (processed or explicitly excluded where policy permits). Failed, missing, unassessed, contradictory or excluded-but-required evidence blocks ordinary completion unless the policy explicitly permits a qualified result; never infer absence from an incomplete upload. `completed` is a computed policy outcome over a frozen manifest revision, not a mutable user-provided boolean. JSONB snapshots may project this record but are not a substitute for immutable history.

## Decision: deterministic promotion and conflict handling

The transitions are `candidate` → `evidence_grounded` → `review_ready` → `approved_conclusion`. A transition is an explicit use case, not an agent output. Unknown policy, missing authority, missing/stale evidence and inconsistent revisions **fail closed**.

- Promotion to `evidence_grounded`: at least one link to an authorized immutable anchor resolves, fidelity is `matched` for an asserted quote/value, and an assessment of semantic relation to the current statement revision is recorded. The state means evidence attached and assessed, **not verified true**.
- Promotion to `review_ready`: all relied-upon links resolve with required fidelity; every required issue is accounted for; current manifest and policy revisions are pinned; any `contradicts`, `qualifies`, `inconclusive` or `not_assessed` links remain visible as unresolved/qualified issues. The review packet can be ready with disclosed conflicts; it is not an approved conclusion.
- Promotion to `approved_conclusion`: requires authorized, explicit human review; complete ordinary coverage under effective policy; one or more supporting links for each material finding; a policy-level sufficiency result calculated from the **set of eligible links** (individual insufficient links may combine, but do not silently become sufficient); no unresolved material contradiction, qualification or missing assessment for the unqualified statement. The reviewer approves the exact frozen statement, source/representation/link revisions, scope/manifest revision and policy version.
- Contradictions and qualifications are never discarded by a higher number of supporting passages. They require a traceable reconciliation: correct the claim, add qualifying language, or leave it unresolved; record assessor and rationale. A materially contradicted or unsupported *unqualified* claim cannot become `approved_conclusion`.
- For policy-authorized business risk acceptance, record a separate `BUSINESS_EXCEPTION_ACCEPTED` workflow disposition with permission, reason, actor, affected unresolved issues and decision snapshot. This may close the operational workflow but **never** changes evidence support/fidelity or authorizes `approved_conclusion`. A decision export must disclose the unresolved status.

No AI/model confidence or agent completion report may authorize any transition. The application checks actor role, action scope, resource ownership and separation-of-duties policy (if configured) using **trusted server-side identity**, not user-provided `actor_id` or `tenant_id`.

## Decision: provenance and retry safety

Each consequential event records trusted actor and tenant scope, subject and previous/new states, source and representation revisions, scope/manifest/assessment/policy versions, rationale, UTC event time, immutable input fingerprint and idempotency key. For retries, the same key + identical fingerprint returns the recorded result; the same key with a different fingerprint returns a conflict. Reject stale optimistic revisions with a structured conflict. An authorized reviewer decision and its audit event must commit atomically with durable state in production; failed audit persistence prevents acknowledgement. In-memory hash chains are not durable and cannot guarantee anti-truncation.

## API, enforcement stages and tests

- Use `401` for missing authentication, `403` for insufficient authorization, `409` for stale revision, invalid transition or incomplete coverage, and `422` for malformed data. Tenant-nonexistent resources may be intentionally hidden with `404`; never use an HTTP status code in place of actual authorization.
- Stage 1: pure deterministic domain/port models, in-memory authorization test doubles, positive and negative transition tests, contradictory-link aggregation, omission tests, duplicate idempotency handling and policy snapshots.
- Stage 2: actual trusted authorization, tenant-scoped persistence, atomic state+audit, crash/restart/rollback fault injection, durable idempotency, and audit history protections.
- The `contracts/kernel-api.v2.proposal.json` file is a **design outline, not OpenAPI or JSON Schema**. KRN-109 requires field-level typed contracts, executable validators, transition/error matrices and example payload contract tests before enabling real v2 endpoints.

## Boundary

Agent task completion, human evidence approval and business exception acceptance are different records. No agent harness, HTTP client, storage adapter or sector may bypass the application promotion gate.
