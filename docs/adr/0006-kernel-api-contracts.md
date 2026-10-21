# ADR 0006: Evidence Kernel contracts and verification authority

Status: Proposed — human review required before merge
Date: 2026-10-21

## Context

The kernel is reusable across sectors. Evidence source matching must not become a legal, financial or factual truth verdict. An HTTP adapter is optional; core logic must remain usable without it.

## Decision

1. Keep source snapshots and extracted claims immutable and independently identified by tenant scope and document version.
2. Treat exact quote matching as a statement about a captured source representation only.
3. Record corroboration, contradiction and reviewer disposition independently, without changing original extracted claims.
4. Define persistence contracts in the kernel; implementations live in adapters.
5. Resolve tenant scope in a trusted application boundary. An absent resolver fails closed. Never accept an arbitrary tenant header as production authorization.
6. Public contract changes require versioned schemas, negative tests, consumer impact review and a separate human approval before merge.

## Consequences

The in-memory reference adapter is intentionally non-durable. It does not establish user authentication, legal authorization, external source authenticity or production audit guarantees. Stage 0 checks define required evidence but cannot establish that tests passed until run on the committed branch.

## Alternatives rejected

- One mutable verified flag: collapses independent states.
- Framework models inside the kernel: violates dependency direction.
- A caller-controlled tenant header: insecure for multi-tenant production use.

## Acceptance

Architecture negative-control, isolated tenant tests, immutable-source tests, OpenAPI compatibility and complete locked test suite must pass before merge.
