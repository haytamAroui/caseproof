# ADR 0009 — Coverage ledger, promotion gate and provenance

Status: Proposed — human review required
Date: 2026-10-21

## Decision: Coverage
An investigation declares its scope: required questions/issues, expected document versions, processing attempts, exclusions, missing evidence and contradictions. A processed-document marker is not proof that an issue was answered. Exclusions require reason, authorization and immutable audit record. Coverage completion is evaluated against an explicit versioned workflow policy. A JSONB manifest may be a projection, not the sole event history.

## Decision: Promotion
Candidate -> evidence-grounded -> review-ready -> approved conclusion are distinct transitions, each with policy checks. An approved conclusion requires resolvable anchors, required fidelity/support/sufficiency checks, completed coverage policy and authorized human review. Inconclusive or contradicted evidence cannot be silently relabeled. An authorized exception disposition may resolve a business workflow with a recorded rationale while preserving the underlying insufficient/contradicted status and unresolved issues. Overrides require explicit permissions and audit.

## Decision: Provenance
Record actor, trusted tenant scope, subject, event kind, source version, policy version, rationale and idempotency key as appropriate. In production, durable state mutation and audit event must be atomic. An in-memory hash chain is a reference mechanism only: it does not provide restart durability or externally anchored anti-truncation guarantees.

## API and tests
Use structured 409 for invalid transitions and 403 for unauthorized operations; never rely on HTTP status codes as authorization. Fail closed on missing evidence and policy ambiguity. Test unauthorized approval, incomplete coverage, duplicate review, conflicting evidence, explicit exception disposition, tampering, cross-tenant references, crash/retry and rollback. Stage 2 owns durable fault injection.

## Boundary
No agent model or framework may bypass the application promotion gate. Agent task completion and evidence approval are separate records.
