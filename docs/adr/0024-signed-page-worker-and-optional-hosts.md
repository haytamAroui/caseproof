# ADR 0024 — Signed resumable page worker and optional channel hosts

Status: implementation candidate authorized by owner continuation on 31 October 2026.
Extends ADR 0023's non-goals only to development implementation/testing of hosted
MCP and Word consumers. No production deployment or confidential-data approval.

## Durable page worker design for review

| Entity | Binding and constraints | Access/lifecycle |
|---|---|---|
| `page_jobs` | Composite org/case/request PK; server-derived actor; immutable manifest hash and bundle signature; absolute deadline; queued/running/succeeded/cancelled; lease UUID/expiry; finite claims | FK to case with cascade; RLS enabled; no direct client grants |
| `page_results` | Composite job/page key; immutable serialized artifact and hash; source version/hash/physical page from immutable manifest; bounded per-page/total bytes | FK to job with cascade; RLS enabled; no direct client grants |
| `page_job_events` | Append-only event number and closed operation/state, no document text | FK to job with cascade; same private boundary; required event write in transaction |

One narrow signed RPC derives actor/org, checks nonanonymous Auth, active membership
and reviewer matter permissions, retention and current bundle. It locks the case,
current grant and job in consistent order. No client actor/org or global job list.
Every enqueue/claim/heartbeat/page write/read/finish/cancel repeats authorization.
An expired or replaced lease fences old writers. Current input signature mismatch
blocks completion. Idempotent enqueue and immutable per-page writes reject conflicts.
Indexes: job PK for scoped access, result PK for exact page reads, event PK for
ordered history; no global tenant index or arbitrary JSON GIN.

Signed clients can request work and store candidate processing artifacts, never
approve evidence. Page artifacts are HMAC-sealed by the trusted server worker and
revalidated on read; a processing status cannot confer fidelity or semantic support.
No bearer or refresh credential is persisted. A worker resumes with a fresh signed
session, the same manifest and a new lease. Existing service credentials are not
used to bypass matter authorization. OCR remains local and sandboxed; worker
network is limited to signed Supabase reads/writes outside parser/OCR subprocesses.

Apply only after disposable SQL adversarial tests and independent read-only review.
Rollback: disable development route/worker and revoke RPC execute; preserve artifacts
until scoped retention/erasure; no destructive rollback or rewriting originals.
New case-child FKs cascade under the existing run-owned cleanup and retention path.
Test audit failure rollback, cross-matter/actor denial, revocation, stale lease,
input mutation, cancellation, absolute deadline and cold-process resume.

## Optional hosted MCP

Resource server target is MCP 2026-07-28: independent POST requests, per-request
version/capabilities, mirrored-header validation, Origin checks, no session IDs.
Only read-only canonical tools. Verify OAuth issuer, exact resource audience,
expiry, scope and client binding; protected-resource metadata points to the
configured authorization server. A normal Supabase application token must not be
silently accepted as an MCP-resource token. A host-controlled resolver supplies a
current downstream signed session and separately approved destination release.
No token passthrough to a different resource and no automatic consent.

## Word and external review

Word consumes the same frozen report; host selection/reopen and document identity
need actual supported Word evidence. A browser simulation is not Word acceptance.
External security approval needs a named independent reviewer, exact build/scope,
findings and disposition. Internal agent review and green CI are engineering evidence.
Prepare the reproducible package; do not invent an external approval or contact
reviewers without explicit person-directed authorization.

## Sources

- https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- https://supabase.com/docs/guides/api/securing-your-api
