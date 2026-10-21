# ExceptionDesk — Database Engineering Standard v1

**Status:** Proposed architecture baseline; schema and migration implementation require separate review. **Authority:** `CONSTITUTION.md` and accepted ADRs prevail.

## Scope and ownership
- PostgreSQL is the source of truth for relational state, authorization membership, transactions and audit metadata. Preserve original evidence bytes in private object storage with versioned references and SHA-256 integrity metadata.
- The Evidence Kernel stays pure Python and sector-neutral; no SQL, ORM, Supabase, HTTP, JWT, finance or dispute dependencies.
- Supabase Auth owns identities. Organization memberships and action-specific permissions are resolved by trusted server-side logic. Never authorize from user-editable metadata or a client-supplied tenant header.
- Select and document one RLS connection strategy: user-scoped Supabase JWT where feasible, or a carefully reviewed least-privilege PostgreSQL role with trusted transaction identity. A custom PostgreSQL setting alone is not an authorization boundary. Test policies using actual runtime privileges.

## Logical entities — not a migration specification
- Identity: `organizations`, `organization_members`, `organization_invitations`.
- Evidence sources: `documents`, `document_versions`.
- Assertions: `claims`, `claim_sources`.
- Assessments: `source_verifications`, `claim_assessments`, `review_decisions`.
- Operations: `audit_events`, `idempotency_records`.
- Workflow `cases` belongs outside the pure Evidence Kernel. Do not create sector-specific schemas during Stage 0.
- Extracted claims are assertions, **not proven facts**. Source verification, corroboration and human disposition are independent.

## Constraints, typing and provenance
1. Use snake_case, native PostgreSQL types, typed constraints, UTC-aware timestamps and explicit foreign keys.
2. Tenant-owned rows require non-null `org_id`; parent-child references across tenant-owned tables require composite tenant-scoped foreign keys and supporting unique keys. Global reference tables are exempt where appropriate.
3. Prefer UUIDv7 for new application-owned identifiers when supported; preserve Supabase Auth user IDs. Do not assume a particular PostgreSQL version.
4. Track `correlation_id` on operations and audit events; distinguish it from `causation_id` and idempotency keys. Do not mandate correlation IDs on all reference rows.
5. Actor identity consists of actor type plus optional user/service ID. Never store `SYSTEM` in a UUID field.
6. Document versions are immutable. Source links include version, location, parser/OCR version and extraction provenance. A SHA-256 match demonstrates byte consistency, not source authenticity or factual truth.
7. Use JSONB only for genuinely variable versioned data, with validation. Use typed columns for important invariants and frequently queried attributes.

## Authorization, audit and lifecycle
1. Enforce tenant authorization in the application and database, and test cross-tenant reads, writes, joins, background jobs and storage access.
2. Create organizations and their owner memberships in one transaction. Invitation acceptance checks invited identity, expiry, permission and replay protection.
3. Audit events are append-only under runtime privileges: deny UPDATE/DELETE, include event schema version, actor, timestamp, correlation and safe metadata. This is not inherently tamper-proof against privileged administrators.
4. Persist required audit records transactionally with consequential state changes; fail the operation if audit persistence fails.
5. Define soft deletion, retention, legal holds, lawful erasure and object lifecycle explicitly; immutability does not override privacy requirements.

## Performance and migration governance
- Explicit column projections; avoid N+1 queries; bound list responses. Prefer cursor/keyset pagination for large histories.
- Index tenant access paths and foreign keys based on actual query plans. No blanket GIN index on JSONB.
- Choose one authoritative migration system for application tables. Require reviewed forward migrations, tested recovery and explicit human approval for destructive or security-sensitive changes.
- Stage 0 is design-only: no database schema, migrations or production resources without approval.

## Mandatory agent workflow
Before changing SQL, ORM models, repository adapters, RLS, Supabase Storage metadata, indexes, migrations or data-access APIs, read this document, `AGENTS.md`, `CONSTITUTION.md` and applicable ADRs. Present an ERD, tenant relationships, RLS/access strategy, constraints, transaction boundaries, index rationale and migration/recovery plan for review. Execute negative tests for cross-tenant access, revoked membership, concurrent writes, unauthorized mutation and audit failure; never fabricate test results. Apply cloud-first verification policy C25.
