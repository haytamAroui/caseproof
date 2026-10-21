# ADR 0009 — Coverage accounting and controlled conclusion promotion
Status: Proposed — human review required
Date: 2026-10-21

## Coverage contract
Every investigation declares a versioned scope: required questions, expected source versions, relevant exclusions, processing tasks and acceptance policy. Track inventory, attempted/processed inputs, issue-level findings, gaps, contradictions, exclusions, and reviewer-authorized waivers separately. PROCESSED means a processing task completed, not that evidence was understood or sufficient. A document skip requires authority, reason, timestamp, source/version, and append-only event; it never silently satisfies an unresolved required issue. JSONB may be a projection, not the only authoritative audit history.

## Promotion contract
Candidate/extracted/checked/reviewed/approved are distinct states. Approval requires trusted actor authorization, explicit policy, sufficient coverage, required source checks and an auditable review decision. Contradicted or insufficient findings remain so even when a business exception disposition is authorized. An override may authorize a narrowly scoped disposition with rationale and recorded authority, but must never mutate evidence status, hide unresolved gaps or imply factual truth. Reject invalid transitions with structured 409 responses; authorization failures with 403 at the HTTP boundary.

## Durability boundary
Stage 1 specifies pure domain rules and ports; Stage 2 must commit evidence transitions and provenance atomically, with idempotency, recovery and external integrity/retention assumptions documented. An in-memory hash chain alone is not a durable audit guarantee.

## Required tests
Unprocessed required document; processed but unanswered issue; unauthorized skip; approved exclusion; stale coverage snapshot; conflicting evidence; attempted self-approval; missing rationale; unauthorized reviewer; idempotent retry; audit-write rollback; cross-tenant isolation.
