# ADR 0007 — Persistence boundary for Evidence Kernel

Status: Proposed (human review before merge)
Date: 2026-10-21

## Decision

The Evidence Kernel domain owns sector-neutral evidence types and repository protocols, but no SQL, Supabase, HTTP or provider code. In-memory implementations are reference adapters, not durable production storage.

- Tenant scope is resolved by an authorized application boundary, not user-supplied headers.
- Source identity is a stable document ID, version ID and content digest.
- Claims reference immutable source versions. Quote matching proves text presence, not authenticity or truth.
- Corroboration and human decisions are separate append-only events.
- Future persistence adapters must provide tenant isolation, immutable provenance, idempotency, atomic audit writes and crash recovery.
- Any durable schema or migration requires review of docs/standards/database-v1.md and a separate task.

## Consequences

No database is introduced in Stage 0. The in-memory store is not appropriate for production and does not satisfy durable audit or retention requirements.

## Required future tests

Cross-tenant isolation, duplicate ingestion, hash mismatch, concurrent append, rollback on audit failure, restart recovery, and authorization failures. This ADR alone does not prove those tests pass.
